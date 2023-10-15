/*
    Copyright © 2023 Aleksandr Mezin

    This file is part of ddterm GNOME Shell extension.

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
*/

'use strict';

/* exported WindowPage TerminalPage ShortcutsPage MiscPage */

const { GObject, Gio, Adw } = imports.gi;
const Me = imports.misc.extensionUtils.getCurrentExtension();

const Page = GObject.registerClass({
    Properties: {
        'settings': GObject.ParamSpec.object(
            'settings',
            '',
            '',
            GObject.ParamFlags.READWRITE | GObject.ParamFlags.CONSTRUCT_ONLY,
            Gio.Settings
        ),
        'gettext-context': GObject.ParamSpec.jsobject(
            'gettext-context',
            '',
            '',
            GObject.ParamFlags.READWRITE | GObject.ParamFlags.CONSTRUCT_ONLY
        ),
    },
}, class DDTermPrefsPage extends Adw.PreferencesPage {
    add_widget(widget_type) {
        const widget = new widget_type({
            settings: this.settings,
            gettext_context: this.gettext_context,
        });

        const group = new Adw.PreferencesGroup({
            title: widget.title,
        });

        group.add(widget);
        this.add(group);
    }
});

var WindowPage = GObject.registerClass({
}, class DDTermWindowPrefsPage extends Page {
    _init(params) {
        super._init({
            name: 'window',
            icon_name: 'preferences-desktop-display',
            ...params,
        });

        this.title = this.gettext_context.gettext('Window');

        [
            Me.imports.ddterm.pref.positionsize.Widget,
            Me.imports.ddterm.pref.behavior.Widget,
            Me.imports.ddterm.pref.animation.Widget,
            Me.imports.ddterm.pref.tabs.Widget,
        ].forEach(widget_type => this.add_widget(widget_type));
    }
});

var TerminalPage = GObject.registerClass({
}, class DDTermTerminalPrefsPage extends Page {
    _init(params) {
        super._init({
            name: 'terminal',
            icon_name: 'utilities-terminal',
            ...params,
        });

        this.title = this.gettext_context.gettext('Terminal');

        [
            Me.imports.ddterm.pref.text.Widget,
            Me.imports.ddterm.pref.colors.Widget,
            Me.imports.ddterm.pref.command.Widget,
            Me.imports.ddterm.pref.scrolling.Widget,
            Me.imports.ddterm.pref.compatibility.Widget,
        ].forEach(widget_type => this.add_widget(widget_type));
    }
});

var ShortcutsPage = GObject.registerClass({
}, class DDTermShortcutsPrefsPage extends Page {
    _init(params) {
        super._init({
            name: 'shortcuts',
            icon_name: 'preferences-desktop-keyboard-shortcuts',
            ...params,
        });

        this.title = this.gettext_context.gettext('Keyboard Shortcuts');

        this.add_widget(Me.imports.ddterm.pref.shortcuts.Widget);
    }
});

var MiscPage = GObject.registerClass({
}, class DDTermMiscPrefsPage extends Page {
    _init(params) {
        super._init({
            name: 'misc',
            icon_name: 'preferences-other',
            ...params,
        });

        this.title = this.gettext_context.gettext('Miscellaneous');

        this.add_widget(Me.imports.ddterm.pref.panelicon.Widget);
    }
});
