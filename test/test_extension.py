import base64
import collections
import contextlib
import functools
import itertools
import logging
import pathlib
import queue
import subprocess
import threading
import time

import allpairspy
import filelock
import pytest
import wand.image
from pytest_html import extras

from . import container_util, dbus_util


LOGGER = logging.getLogger(__name__)

Rect = collections.namedtuple('Rect', ('x', 'y', 'width', 'height'))
MonitorConfig = collections.namedtuple('MonitorConfig', ['current_index', 'setting'])

TEST_SRC_DIR = pathlib.Path(__file__).parent.resolve()
SRC_DIR = TEST_SRC_DIR.parent
EXTENSION_UUID = 'ddterm@amezin.github.com'
USER_NAME = 'gnomeshell'
PKG_PATH = f'/home/{USER_NAME}/.local/share/gnome-shell/extensions/{EXTENSION_UUID}'

MAXIMIZE_MODES = ['not-maximized', 'maximize-early', 'maximize-late']
HORIZONTAL_RESIZE_POSITIONS = ['left', 'right']
VERTICAL_RESIZE_POSITIONS = ['top', 'bottom']
POSITIONS = VERTICAL_RESIZE_POSITIONS + HORIZONTAL_RESIZE_POSITIONS
SIZE_VALUES = [0.5, 0.9, 1.0]
SMALL_SCREEN_SIZE_VALUES = [0.8, 0.85, 0.91]
MORE_SIZE_VALUES = [0.31, 0.36, 0.4] + SMALL_SCREEN_SIZE_VALUES


def mkpairs(*args, **kwargs):
    return list(allpairspy.AllPairs(*args, **kwargs))


@pytest.fixture(scope='session')
def xvfb_fbdir(tmpdir_factory):
    return tmpdir_factory.mktemp('xvfb')


class ScreenshotContextManager(contextlib.AbstractContextManager):
    def __init__(self, failing_only, screen_path, extra):
        super().__init__()
        self.failing_only = failing_only
        self.screen_path = screen_path
        self.extra = extra

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None and self.failing_only:
            return

        xwd_blob = pathlib.Path(self.screen_path).read_bytes()

        with wand.image.Image(blob=xwd_blob, format='xwd') as img:
            png_blob = img.make_blob('png')

        self.extra.append(extras.png(base64.b64encode(png_blob).decode('ascii')))


@pytest.fixture
def screenshot(xvfb_fbdir, extra, pytestconfig):
    return ScreenshotContextManager(
        pytestconfig.getoption('--screenshot-failing-only'),
        xvfb_fbdir / 'Xvfb_screen0',
        extra
    )


@pytest.mark.runtest_cm.with_args(lambda item, when: item.cls.journal_context(item, when))
class CommonTests:
    GNOME_SHELL_SESSION_NAME: str
    N_MONITORS: int
    PRIMARY_MONITOR = 0

    current_container: container_util.Container = None
    current_dbus_interface = None

    @classmethod
    def journal_message(cls, msg):
        if cls.current_dbus_interface:
            cls.current_dbus_interface.LogMessage('(s)', msg)
        else:
            cls.current_container.exec('systemd-cat', input=msg.encode())

    @classmethod
    def journal_sync(cls, msg):
        buffer = queue.SimpleQueue()
        pattern = msg.encode()
        grep = container_util.QueueOutput(buffer, lambda line: pattern in line)

        with cls.current_container.console.with_output(grep):
            cls.journal_message(msg)

            try:
                buffer.get(timeout=1)
            except queue.Empty:
                raise TimeoutError()

    @classmethod
    @contextlib.contextmanager
    def journal_context(cls, item, when):
        assert cls is not CommonTests

        if cls.current_container is not None:
            cls.journal_message(f'Beginning of {item.nodeid} {when}')

        try:
            yield

        finally:
            if cls.current_container is not None:
                try:
                    cls.journal_sync(f'End of {item.nodeid} {when}')
                except Exception:
                    LOGGER.exception("Can't sync journal")

    @classmethod
    def mount_configs(cls):
        return ['/etc/systemd/system/xvfb@.service.d/fbdir.conf']

    @pytest.fixture(scope='class')
    def container(self, podman, container_image, xvfb_fbdir, global_tmp_path, request):
        assert request.cls is not CommonTests
        assert request.cls.current_container is None

        volumes = [
            (SRC_DIR, PKG_PATH, 'ro'),
            (xvfb_fbdir, '/xvfb', 'rw')
        ]

        volumes.extend(
            (pathlib.Path(f'{TEST_SRC_DIR}/{path}'), pathlib.PurePath(path), 'ro')
            for path in request.cls.mount_configs()
        )

        cap_add = [
            'SYS_NICE',
            'SYS_PTRACE',
            'SETPCAP',
            'NET_RAW',
            'NET_BIND_SERVICE',
            'DAC_READ_SEARCH',
        ]

        with filelock.FileLock(global_tmp_path / 'container-starting.lock') as lock:
            c = container_util.Container.run(
                podman,
                '--rm',
                '-P',
                '--log-driver=none',
                f'--cap-add={",".join(cap_add)}',
                *itertools.chain.from_iterable(
                    ('-v', ':'.join(str(part) for part in parts))
                    for parts in volumes
                ),
                container_image,
            )

        try:
            c.attach()
            request.cls.current_container = c

            c.exec('busctl', '--system', '--watch-bind=true', 'status', stdout=subprocess.DEVNULL)
            c.exec('systemctl', 'is-system-running', '--wait')

            yield c

        finally:
            request.cls.current_container = None
            c.kill()

    @pytest.fixture(scope='class')
    def user_env(self, container):
        bus_address = container.exec(
            'su', '-c', 'echo $DBUS_SESSION_BUS_ADDRESS', '-', USER_NAME, stdout=subprocess.PIPE
        ).stdout.rstrip(b'\n').decode()
        return dict(user=USER_NAME, env=dict(DBUS_SESSION_BUS_ADDRESS=bus_address))

    @pytest.fixture(scope='class')
    def gnome_shell_session(self, container, user_env):
        container.exec('systemctl', '--user', 'start', f'{self.GNOME_SHELL_SESSION_NAME}@:99', **user_env)
        return self.GNOME_SHELL_SESSION_NAME

    @pytest.fixture(scope='class')
    def bus_connection(self, container, user_env):
        while container.exec(
            'busctl', '--user', '--watch-bind=true', 'status',
            stdout=subprocess.DEVNULL, check=False, **user_env
        ).returncode != 0:
            time.sleep(0.1)

        hostport = container.inspect('{{json .NetworkSettings.Ports}}')['1234/tcp'][0];
        host = hostport['HostIp'] or '127.0.0.1'
        port = hostport['HostPort']

        with contextlib.closing(dbus_util.connect_tcp(host, port)) as c:
            yield c

    @pytest.fixture(scope='class')
    def shell_extensions_interface(self, bus_connection, gnome_shell_session):
        return dbus_util.wait_interface(
            bus_connection,
            name='org.gnome.Shell',
            path='/org/gnome/Shell',
            interface='org.gnome.Shell.Extensions',
        )

    @pytest.fixture(scope='class')
    def extension_test_interface(self, bus_connection, shell_extensions_interface, request):
        assert request.cls is not CommonTests
        assert request.cls.current_dbus_interface is None

        shell_extensions_interface.EnableExtension('(s)', EXTENSION_UUID)

        iface = dbus_util.wait_interface(
            bus_connection,
            name='org.gnome.Shell',
            path='/org/gnome/Shell/Extensions/ddterm',
            interface='com.github.amezin.ddterm.ExtensionTest'
        )
        request.cls.current_dbus_interface = iface

        try:
            yield iface

        finally:
            request.cls.current_dbus_interface = None

    @pytest.fixture(scope='class', autouse=True)
    def extension_setup(self, extension_test_interface):
        assert extension_test_interface.get_cached_property('PrimaryMonitor').unpack() == self.PRIMARY_MONITOR
        assert extension_test_interface.get_cached_property('NMonitors').unpack() == self.N_MONITORS

        extension_test_interface.Setup()

    @pytest.fixture(scope='class')
    def monitors_geometry(self, extension_test_interface):
        return [
            Rect(*extension_test_interface.GetMonitorGeometry('(i)', index))
            for index in range(self.N_MONITORS)
        ]

    @pytest.fixture(scope='class')
    def monitors_scale(self, extension_test_interface):
        return [
            extension_test_interface.GetMonitorScale('(i)', index)
            for index in range(self.N_MONITORS)
        ]

    @pytest.fixture(scope='class')
    def shell_version(self, shell_extensions_interface):
        return shell_extensions_interface.get_cached_property('ShellVersion').unpack()

    @pytest.mark.parametrize(
        ['window_size', 'window_maximize', 'window_pos'],
        mkpairs([MORE_SIZE_VALUES, MAXIMIZE_MODES, VERTICAL_RESIZE_POSITIONS])
    )
    def test_show_v(self, extension_test_interface, window_size, window_maximize, window_pos, monitor_config, screenshot):
        with screenshot:
            extension_test_interface.TestShow('(dssis)', window_size, window_maximize, window_pos, monitor_config.current_index, monitor_config.setting)

    def test_show_h(self, extension_test_interface, window_size, window_maximize, window_pos, monitor_config, monitors_geometry, monitors_scale, screenshot):
        if monitor_config.setting == 'primary':
            target_monitor = self.PRIMARY_MONITOR
        else:
            target_monitor = monitor_config.current_index

        with screenshot:
            extension_test_interface.TestShow('(dssis)', window_size, window_maximize, window_pos, monitor_config.current_index, monitor_config.setting)

    @pytest.mark.parametrize(
        ['window_size', 'window_maximize', 'window_size2', 'window_pos'],
        mkpairs([SIZE_VALUES, MAXIMIZE_MODES, SIZE_VALUES, POSITIONS])
    )
    @pytest.mark.flaky
    def test_resize_xte(self, extension_test_interface, window_size, window_maximize, window_size2, window_pos, monitor_config, shell_version, screenshot):
        version_split = tuple(int(x) for x in shell_version.split('.'))
        if version_split < (3, 39):
            if monitor_config.current_index == 1 and window_pos == 'bottom' and window_size2 == 1:
                pytest.xfail('For unknown reason it fails to resize to full height on 2nd monitor')

        with screenshot:
            extension_test_interface.TestResizeXte('(dsdsis)', window_size, window_maximize, window_size2, window_pos, monitor_config.current_index, monitor_config.setting)

    @pytest.mark.parametrize(
        ['window_pos', 'window_pos2', 'window_size'],
        mkpairs([POSITIONS, POSITIONS, SIZE_VALUES], filter_func=lambda p: (len(p) < 2) or (p[0] != p[1]))
    )
    def test_change_position(self, extension_test_interface, window_size, window_pos, window_pos2, monitor_config, screenshot):
        with screenshot:
            extension_test_interface.TestChangePosition('(dssis)', window_size, window_pos, window_pos2, monitor_config.current_index, monitor_config.setting)

    @pytest.mark.parametrize(
        ['window_size', 'window_maximize', 'window_pos'],
        mkpairs([SIZE_VALUES, MAXIMIZE_MODES, POSITIONS])
    )
    def test_unmaximize(self, extension_test_interface, window_size, window_maximize, window_pos, monitor_config, screenshot):
        with screenshot:
            extension_test_interface.TestUnmaximize('(dssis)', window_size, window_maximize, window_pos, monitor_config.current_index, monitor_config.setting)

    @pytest.mark.parametrize(
        ['window_size', 'window_size2', 'window_pos'],
        mkpairs([SIZE_VALUES, SIZE_VALUES, POSITIONS])
    )
    def test_unmaximize_correct_size(self, extension_test_interface, window_size, window_size2, window_pos, monitor_config, screenshot):
        with screenshot:
            extension_test_interface.TestUnmaximizeCorrectSize('(ddsis)', window_size, window_size2, window_pos, monitor_config.current_index, monitor_config.setting)

    @pytest.mark.parametrize(
        ['window_size', 'window_size2', 'window_pos'],
        mkpairs([SIZE_VALUES, SIZE_VALUES, POSITIONS], filter_func=lambda p: (len(p) < 2) or (p[0] != p[1]))
    )
    def test_unmaximize_on_size_change(self, extension_test_interface, window_size, window_size2, window_pos, monitor_config, screenshot):
        with screenshot:
            extension_test_interface.TestUnmaximizeOnSizeChange('(ddsis)', window_size, window_size2, window_pos, monitor_config.current_index, monitor_config.setting)


class LargeScreenMixin(CommonTests):
    @pytest.mark.parametrize(
        ['window_size', 'window_maximize', 'window_pos'],
        mkpairs([MORE_SIZE_VALUES, MAXIMIZE_MODES, HORIZONTAL_RESIZE_POSITIONS])
    )
    @functools.wraps(CommonTests.test_show_h)
    def test_show_h(self, *args, **kwargs):
        super().test_show_h(*args, **kwargs)


class SmallScreenMixin(CommonTests):
    @pytest.mark.parametrize(
        ['window_size', 'window_maximize', 'window_pos'],
        mkpairs([SMALL_SCREEN_SIZE_VALUES, MAXIMIZE_MODES, HORIZONTAL_RESIZE_POSITIONS])
    )
    @functools.wraps(CommonTests.test_show_h)
    def test_show_h(self, *args, **kwargs):
        super().test_show_h(*args, **kwargs)


@pytest.mark.parametrize('monitor_config', [
    MonitorConfig(0, 'current')
])
class SingleMonitorTests(CommonTests):
    N_MONITORS = 1


@pytest.mark.parametrize('monitor_config', [
    MonitorConfig(1, 'primary'),
    MonitorConfig(1, 'current'),
    # MonitorConfig(0, 'current'), # not interesting
])
class DualMonitorTests(CommonTests):
    N_MONITORS = 2


class TestXSession(SingleMonitorTests, LargeScreenMixin):
    GNOME_SHELL_SESSION_NAME = 'gnome-xsession'


class TestWayland(SingleMonitorTests, LargeScreenMixin):
    GNOME_SHELL_SESSION_NAME = 'gnome-wayland-nested'


class TestWaylandHighDpi(SingleMonitorTests, SmallScreenMixin):
    GNOME_SHELL_SESSION_NAME = 'gnome-wayland-nested'

    @classmethod
    def mount_configs(cls):
        return super().mount_configs() + [
            '/etc/systemd/user/gnome-wayland-nested@.service.d/mutter-highdpi.conf'
        ]


class TestWaylandDualMonitor(DualMonitorTests, SmallScreenMixin):
    GNOME_SHELL_SESSION_NAME = 'gnome-wayland-nested'

    @classmethod
    def mount_configs(cls):
        return super().mount_configs() + [
            '/etc/systemd/user/gnome-wayland-nested@.service.d/mutter-dual-monitor.conf'
        ]
