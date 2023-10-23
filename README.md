# Another Drop Down Terminal Extension for GNOME Shell

[<img src="docs/get-it-on-ego.svg?sanitize=true" alt="Get it on GNOME Extensions" height="100" align="middle">][extensions.gnome.org]

<img src="docs/screenshots/dropdown.gif" />

Inspired by

- https://github.com/bigbn/drop-down-terminal-x

- https://github.com/Guake/guake

## Distinguishing features

- Runs on Wayland natively

- Terminal window can be resized by dragging the border with mouse

- `Preferences` window with a lot of different settings

<img src="docs/screenshots/prefs.gif" />

## Review by [TechHut](https://www.youtube.com/channel/UCjSEJkpGbcZhvo0lr-44X_w)

[![my favorite GNOME extension](http://img.youtube.com/vi/tF6_FJYca64/0.jpg)](http://www.youtube.com/watch?v=tF6_FJYca64)

## Installing

The easiest way to install the extension is to go to [extensions.gnome.org].

However, the review process on [extensions.gnome.org] is sometimes slow.
A new release may be available here on GitHub, but not on
[extensions.gnome.org] yet.

[extensions.gnome.org]: https://extensions.gnome.org/extension/3780/ddterm/

If you want to install from GitHub: see [docs/INSTALL.md](docs/INSTALL.md)

## Contribute

Pull requests are always welcome.

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md).

## Translations

You could help translating the user interface using
[Weblate](https://hosted.weblate.org/engage/gnome-shell-extension-ddterm/),
or by opening a pull request on GitHub.

[![Translation status](https://hosted.weblate.org/widgets/gnome-shell-extension-ddterm/-/multi-auto.svg)](https://hosted.weblate.org/engage/gnome-shell-extension-ddterm/)

See [docs/Translations.md](docs/Translations.md).

## Toggle the terminal through D-Bus

It's possible to toggle the terminal externally through D-Bus. For example,
from command line:

    $ gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell/Extensions/ddterm --method com.github.amezin.ddterm.Extension.Toggle

Or simply show/activate:

    $ gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell/Extensions/ddterm --method com.github.amezin.ddterm.Extension.Activate

## `gapplication`

You could also interact with ddterm through `gapplication` utility:

    $ gapplication action com.github.amezin.ddterm show
    $ gapplication action com.github.amezin.ddterm hide
    $ gapplication action com.github.amezin.ddterm toggle

Open a new tab with the specified working directory:

    $ gapplication launch com.github.amezin.ddterm ~/directory

Or launch a script:

    $ gapplication launch com.github.amezin.ddterm ~/script.sh

## Command line

You can open a new tab from the command line:

    $ com.github.amezin.ddterm -- ssh localhost

See `com.github.amezin.ddterm --help` for options.

You'll need to add
`~/.local/share/gnome-shell/extensions/ddterm@amezin.github.com/bin` to `PATH`.
