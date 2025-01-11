import platform
import sys
import webbrowser
from copy import deepcopy
from functools import partial
from pathlib import Path
from subprocess import getoutput
from typing import Any, Literal

from PyQt6.QtCore import QLocale, QModelIndex, Qt, QTimer, QTranslator
from PyQt6.QtGui import QCloseEvent, QIcon, QKeySequence, QMouseEvent
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                             QDoubleSpinBox, QFrame, QHBoxLayout,
                             QKeySequenceEdit, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMainWindow, QMessageBox,
                             QPushButton, QSizePolicy, QSpacerItem, QSpinBox,
                             QVBoxLayout, QWidget)
from serial.tools.list_ports import comports

try:
    from . import config
    from .actions import auto_activaters
    from .actions.signals_slots import (SignalOrSlot, find_signal_slot,
                                        query_by_device, query_signals_slots)
    from .daemon import Daemon
    from .enums import Issue, Tag
    from .external_styles.breeze import breeze_pyqt6 as _  # noqa: F811
    from .icons import resource as _  # noqa: F811
    from .model import (MODS, Component, Profile, find_device, gen_profile_id,
                        validate_components)
    from .paths import ICONS_PATH, STYLES_PATH
    from .ui.component_editor_ui import Ui_ComponentEditor
    from .ui.create_component_ui import Ui_CreateComponent
    from .ui.macro_action_editor_ui import Ui_MacroActionEditor
    from .ui.macro_editor_ui import Ui_MacroEditor
    from .ui.profile_editor_ui import Ui_ProfileEditor
    from .ui.profiles_ui import Ui_Profiles
    from .ui.settings_ui import Ui_Settings
    from .ui.window_ui import Ui_Microstation
    from .utils import get_device_info
except ImportError:
    import config  # type: ignore[no-redef]
    try:
        from icons import resource as _  # noqa: F401
    except ImportError:
        config.log(
            "Failed to load icons. Did you forget to run the compile-icons "
            "script?"
            "ERROR",
        )
    try:
        from external_styles.breeze import breeze_pyqt6 as _  # noqa: F401,F811
    except ImportError:
        config.log(
            "Failed to load styles. Did you forget to run the compile-styles "
            "script?"
            "ERROR",
        )
    try:
        from ui.component_editor_ui import Ui_ComponentEditor
        from ui.create_component_ui import Ui_CreateComponent
        from ui.macro_action_editor_ui import Ui_MacroActionEditor
        from ui.macro_editor_ui import Ui_MacroEditor
        from ui.profile_editor_ui import Ui_ProfileEditor
        from ui.profiles_ui import Ui_Profiles
        from ui.settings_ui import Ui_Settings
        from ui.window_ui import Ui_Microstation
    except ImportError:
        config.log(
            "Failed to load UI. Did you forget to run the compile-ui script?"
            "ERROR",
        )
    from actions import auto_activaters  # type: ignore[no-redef]  # noqa: F401
    from actions.signals_slots import SignalOrSlot  # type: ignore[no-redef]
    from actions.signals_slots import find_signal_slot  # type: ignore
    from actions.signals_slots import query_by_device  # type: ignore
    from actions.signals_slots import query_signals_slots  # type: ignore
    from daemon import Daemon  # type: ignore[no-redef]  # noqa: F401
    from enums import Issue, Tag  # type: ignore[no-redef]  # noqa: F401
    from model import MODS  # type: ignore[no-redef]
    from model import Component  # type: ignore[no-redef]  # noqa: F401
    from model import Profile  # type: ignore[no-redef]  # noqa: F401
    from model import find_device  # type: ignore[no-redef]  # noqa: F401
    from model import gen_profile_id  # type: ignore[no-redef]  # noqa: F401
    from model import validate_components  # type: ignore[no-redef] # noqa F401
    from paths import ICONS_PATH  # type: ignore[no-redef]  # noqa: F401
    from paths import STYLES_PATH  # type: ignore[no-redef]  # noqa: F401
    from utils import get_device_info  # type: ignore[no-redef]  # noqa: F401


tr = QApplication.translate


def show_error(parent: QWidget, title: str, desc: str) -> int:
    messagebox = QMessageBox(parent)
    messagebox.setIcon(QMessageBox.Icon.Critical)
    messagebox.setWindowTitle(title)
    messagebox.setText(desc)
    messagebox.setStandardButtons(QMessageBox.StandardButton.Ok)
    messagebox.setDefaultButton(QMessageBox.StandardButton.Ok)
    return messagebox.exec()


class Microstation(QMainWindow, Ui_Microstation):  # type: ignore[misc]
    def __init__(
        self,
        daemon: Daemon,
        locales: list[QLocale],
        translators: dict[str, QTranslator],
    ) -> None:
        super().__init__(None)
        self.daemon = daemon
        self.locales = locales
        self.translators = translators
        self.current_translator: QTranslator | None = None

        self.selected_port: str = config.get_config_value("default_port")
        self._previous_comports: list[str] = []
        self._previous_profiles: list[str] = []
        self.selected_profile: Profile | None = None

        self.setupUi(self)
        self.connectSignalsSlots()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(500)

    def refresh(self) -> None:
        self.update_ports()
        self.mcDisplay.setText(
            self.daemon.device.name or tr("Microstation", "Not connected")
        )
        self.update_profile_combo()

    def update_profile_combo(self) -> None:
        profiles = [profile.name for profile in config.PROFILES]
        if profiles == self._previous_profiles:
            return
        self._previous_profiles = profiles
        self.profileCombo.clear()
        for i, profile in enumerate(profiles):
            self.profileCombo.addItem(profile)
            if self.selected_profile and self.selected_profile.name == profile:
                self.profileCombo.setCurrentIndex(i)

    def update_ports(self, force: bool = False) -> None:
        current_comports = [port.device for port in comports()]
        if current_comports == self._previous_comports and not force:
            return
        self._previous_comports = current_comports
        self.menuPort.clear()
        for port in sorted(comports()):
            action = self.menuPort.addAction(
                f"{port.device} ({get_device_info(port)})"
            )
            action.setCheckable(True)
            if port.device == self.selected_port:
                action.setChecked(True)
            action.triggered.connect(partial(self.set_port, port.device))

    def set_port(self, port: str) -> None:
        self.selected_port = port
        self.update_ports(force=True)
        if self.daemon.port != port:
            self.daemon.port = port
            self.daemon.queue_restart()

    def setupUi(self, window: QMainWindow) -> None:
        super().setupUi(window)
        self.setWindowTitle(tr("Microstation", "Microstation"))
        self.update_ports(True)
        self.refresh()

        # Language menu
        self.menuLanguage.clear()
        for locale_ in self.locales:
            action = self.menuLanguage.addAction(locale_.language().name)
            action.triggered.connect(partial(self.change_language, locale_))

        self.change_language(QLocale(config.get_config_value("locale")))

        # Theme menu
        for dir in sorted(STYLES_PATH.iterdir()):
            if dir.is_dir():
                group_name = dir.name
                for sub_theme in sorted(dir.iterdir()):
                    if sub_theme.is_file() or "cache" in sub_theme.name:
                        continue
                    theme_name = sub_theme.name.replace("-", " ").title()
                    action = self.menuTheme.addAction(
                        full_name := f"{group_name.title()} {theme_name}"
                    )
                    if config.get_config_value("theme") == full_name:
                        self.set_style(sub_theme / "stylesheet.qss", full_name)
                    action.triggered.connect(
                        partial(
                            self.set_style,
                            (sub_theme / "stylesheet.qss"),
                            full_name
                        )
                    )

        action = self.menuHelp.addAction(
            QIcon(str(ICONS_PATH / "music.svg")), "Need Help?"
        )
        action.triggered.connect(partial(
            self.open_url,
            "https://archive.org/details/undertaleoriginalsoundtrack/"
        ))

    def connectSignalsSlots(self) -> None:
        self.actionRefresh_Ports.triggered.connect(self.update_ports)
        self.actionRestart_Daemon.triggered.connect(self.daemon.queue_restart)
        self.actionPause.triggered.connect(self.set_paused)
        self.actionRun_in_Background.triggered.connect(self.hide)
        self.actionQuit.triggered.connect(self.full_close)

        self.actionSettings.triggered.connect(self.open_settings)
        self.actionProfiles.triggered.connect(self.open_profiles)
        self.actionMacros.triggered.connect(self.open_macros)

        self.actionThemeDefault.triggered.connect(
            lambda: self.setStyleSheet("")
        )

        self.actionOpenWiki.triggered.connect(partial(
            self.open_url, "https://github.com/TheCheese42/microstation/wiki"
        ))
        self.actionOpenGitHub.triggered.connect(partial(
            self.open_url, "https://github.com/TheCheese42/microstation"
        ))

    def open_url(self, url: str) -> None:
        try:
            webbrowser.WindowsDefault().open(url)  # type: ignore[attr-defined]
        except Exception:
            system = platform.system()
            if system == "Windows":
                getoutput(
                    f"start {url}"
                )
            else:
                getoutput(
                    f"open {url}"
                )

    def open_file(self, path: str | Path) -> None:
        try:
            # Webbrowser module can well be used to open regular file as well.
            # The system will use the default application, for the file type,
            # not necessarily the webbrowser.
            webbrowser.WindowsDefault().open(str(path))  # type: ignore[attr-defined]  # noqa
        except Exception:
            system = platform.system()
            if system == "Windows":
                getoutput(f"start {path}")
            else:
                getoutput(f"open {path}")

    def open_settings(self) -> None:
        dialog = Settings(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_port = dialog.portBox.currentText()
            config.set_config_value("default_port", selected_port)
            self.set_port(selected_port)
            selected_baudrate = dialog.baudrateSpin.value()
            config.set_config_value("baudrate", selected_baudrate)
            if self.daemon.baudrate != selected_baudrate:
                self.daemon.baudrate = selected_baudrate
                self.daemon.queue_restart()
            auto_detect_profiles = dialog.autoDetectCheck.isChecked()
            config.set_config_value(
                "auto_detect_profiles", auto_detect_profiles
            )
            hide_to_tray_startup = dialog.hideToTrayCheck.isChecked()
            config.set_config_value(
                "hide_to_tray_startup", hide_to_tray_startup
            )

    def open_profiles(self) -> None:
        dialog = Profiles(self, deepcopy(config.PROFILES), self.daemon)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config.PROFILES = dialog.profiles
            config.save_profiles(config.PROFILES)
            self.selected_profile = None
            self.refresh()

    def open_macros(self) -> None:
        dialog = MacroEditor(self, deepcopy(config.MACROS))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dialog.reorder_actions()
            config.MACROS = dialog.macros
            config.save_macros(config.MACROS)

    def set_paused(self) -> None:
        self.daemon.set_paused(self.actionPause.isChecked())
        self.actionPause.setText(
            tr("Microstation", "Resume")
            if self.actionPause.isChecked()
            else tr("Microstation", "Pause")
        )

    def set_style(self, path: Path, full_name: str) -> None:
        config.set_config_value("theme", full_name)
        stylesheet = path.read_text("utf-8")
        self.setStyleSheet(stylesheet)

    def change_language(self, locale: QLocale) -> None:
        config.set_config_value("locale", locale.name())
        QLocale.setDefault(locale)
        if self.current_translator:
            if (app := QApplication.instance()) is not None:
                app.removeTranslator(self.current_translator)
        translator = self.translators.get(locale.name())
        if translator:
            if (app := QApplication.instance()) is not None:
                app.installTranslator(translator)
            self.current_translator = translator
        self.retranslateUi(self)

    def closeEvent(self, event: QCloseEvent | None) -> None:
        if event:
            event.ignore()
        self.close()

    def close(self) -> bool:
        self.hide()
        return False

    def full_close(self) -> None:
        config.log("User requested QUIT through GUI", "INFO")
        super().close()
        if instance := QApplication.instance():
            instance.quit()
        sys.exit(0)


class Settings(QDialog, Ui_Settings):  # type: ignore[misc]
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setupUi(self)

    def setupUi(self, *args: Any, **kwargs: Any) -> None:
        super().setupUi(*args, **kwargs)
        self.portBox.clear()
        prev_default = config.get_config_value("default_port")
        cur_index = 0
        for i, port in enumerate(sorted(comports())):
            self.portBox.addItem(port[0])
            if port[0] == prev_default:
                cur_index = i
        self.portBox.setCurrentIndex(cur_index)

        self.baudrateSpin.setValue(config.get_config_value("baudrate"))

        self.autoDetectCheck.setChecked(
            config.get_config_value("auto_detect_profiles")
        )

        self.hideToTrayCheck.setChecked(
            config.get_config_value("hide_to_tray_startup")
        )


class Profiles(QDialog, Ui_Profiles):  # type: ignore[misc]
    def __init__(
        self, parent: QWidget, profiles: list[Profile], daemon: Daemon
    ) -> None:
        super().__init__(parent)
        self.profiles = profiles
        self.daemon = daemon
        self.setupUi(self)
        self.connectSignalsSlots()

    def setupUi(self, *args: Any, **kwargs: Any) -> None:
        super().setupUi(*args, **kwargs)
        self.updateProfileList()

    def updateProfileList(self) -> None:
        self.profilesList.clear()
        self.profilesList.addItems(
            [profile.name for profile in self.profiles]
        )

    def connectSignalsSlots(self) -> None:
        self.addBtn.clicked.connect(self.add_profile)
        self.copyBtn.clicked.connect(self.copy_profile)
        self.editBtn.clicked.connect(self.edit_profile)
        self.deleteBtn.clicked.connect(self.delete_profile)

    def add_profile(self) -> None:
        self.profiles.append(Profile.new(
            gen_profile_id(self.profiles), self.daemon.queue_write
        ))
        self.updateProfileList()

    def copy_profile(self) -> None:
        try:
            selected = self.profilesList.selectedIndexes()[0].row()
        except IndexError:
            return
        self.profiles.append(p := deepcopy(self.profiles[selected]))
        p.name += " (copy)"
        self.updateProfileList()

    def edit_profile(self) -> None:
        try:
            selected = self.profilesList.selectedIndexes()[0].row()
        except IndexError:
            return
        dialog = ProfileEditor(
            self, deepcopy(self.profiles[selected]), self.daemon
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_profile = dialog.profile
            new_profile.name = dialog.nameEdit.text()
            new_profile.auto_activate_priority = dialog.prioritySpin.value()
            self.profiles[selected] = new_profile
            self.updateProfileList()

    def delete_profile(self) -> None:
        try:
            selected = self.profilesList.selectedIndexes()[0].row()
        except IndexError:
            return
        self.profiles.pop(selected)
        self.updateProfileList()


class ProfileEditor(QDialog, Ui_ProfileEditor):  # type: ignore[misc]
    def __init__(
        self, parent: QWidget, profile: Profile, daemon: Daemon
    ) -> None:
        super().__init__(parent)
        self.profile = profile
        self.daemon = daemon
        self.activate_config_widgets: list[QWidget] = []
        self.component_widgets: list[QWidget] = []
        self.setupUi(self)
        self.connectSignalsSlots()

    def setupUi(self, *args: Any, **kwargs: Any) -> None:
        super().setupUi(*args, **kwargs)
        self.nameEdit.setText(self.profile.name)

        self.autoActivateCombo.addItems(
            [tr("ProfileEditor", "Off"), tr("ProfileEditor", "Default")]
        )
        for name in auto_activaters.ACTIVATERS:
            self.autoActivateCombo.addItem(name)
            if self.profile.auto_activate_manager == name:
                self.autoActivateCombo.setCurrentText(name)
                self.set_auto_activate(name, init=True)
        if self.profile.auto_activate_manager is True:
            self.autoActivateCombo.setCurrentText(
                tr("ProfileEditor", "Default")
            )
        elif self.profile.auto_activate_manager is False:
            self.autoActivateCombo.setCurrentText(tr("ProfileEditor", "Off"))

        self.prioritySpin.setValue(self.profile.auto_activate_priority)

        self.setup_components()

    def setup_components(self) -> None:
        self.scrollAreaWidgetContents.setLayout(self.scrollAreaLayout)
        cl = self.componentsVBox
        for widget in self.component_widgets:
            try:
                cl.removeWidget(widget)
            except TypeError:
                # To also remove the Spacer
                cl.removeItem(widget)
        self.component_widgets.clear()

        for i, component in enumerate(self.profile.components):
            name_rest_vbox = QVBoxLayout()
            frame = QFrame()
            frame.setFrameShape(QFrame.Shape.Box)
            name_label = QLabel(component.device.NAME)
            name_font = name_label.font()
            name_font.setPointSize(16)
            name_label.setFont(name_font)
            rest_hbox = QHBoxLayout()
            pins_label = QLabel(tr("ProfileEditor", "Pins:"))
            pins_font = pins_label.font()
            pins_font.setPointSize(14)
            pins_label.setFont(pins_font)
            rest_hbox.addWidget(pins_label)
            for pin in component.pins.values():
                pin_label = QLabel(str(pin))
                pin_font = pin_label.font()
                pin_font.setPointSize(14)
                pin_label.setFont(pin_font)
                pin_label.setStyleSheet(
                    "border-color: rgb(118, 121, 124); border-width: 1px;"
                )
                rest_hbox.addWidget(pin_label)
            rest_hbox.addSpacerItem(QSpacerItem(
                1, 1, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed,
            ))
            edit_btn = QPushButton(tr("ProfileEditor", "Edit"))
            edit_font = edit_btn.font()
            edit_font.setPointSize(14)
            edit_btn.setFont(edit_font)
            edit_btn.clicked.connect(partial(self.edit_component, i))
            rest_hbox.addWidget(edit_btn)
            delete_btn = QPushButton(tr("ProfileEditor", "Delete"))
            delete_font = delete_btn.font()
            delete_font.setPointSize(14)
            delete_btn.setFont(delete_font)
            delete_btn.clicked.connect(partial(self.delete_component, i))
            rest_hbox.addWidget(delete_btn)
            name_rest_vbox.addWidget(name_label)
            name_rest_vbox.addLayout(rest_hbox)
            frame.setLayout(name_rest_vbox)
            self.component_widgets.append(frame)
            cl.addWidget(frame)
        spacer = QSpacerItem(
            1, 1, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding,
        )
        cl.addSpacerItem(spacer)
        self.component_widgets.append(spacer)

    def edit_component(self, index: int) -> None:
        component = self.profile.components[index]
        dialog = ComponentEditor(self, deepcopy(component))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.profile.components[index] = dialog.component
        self.setup_components()

    def delete_component(self, index: int) -> None:
        del self.profile.components[index]
        self.setup_components()

    def connectSignalsSlots(self) -> None:
        self.autoActivateCombo.currentTextChanged.connect(
            self.set_auto_activate
        )
        self.newBtn.clicked.connect(self.new_component)

        self.buttonBox.accepted.connect(self.accept_requested)

    def accept_requested(self) -> None:
        issue, info = validate_components(self.profile.components)
        match issue:
            case Issue.NONE:
                self.accept()
            case Issue.DUPLICATED_PIN:
                show_error(
                    self,
                    tr("ProfileEditor", "Invalid Components"),
                    tr("ProfileEditor", "Your Profile contains invalid "
                       f"Components: Pin {0} was used multiple "
                       "times.").format(info['pin']),
                )
            case Issue.COMPONENT_PINS_NOT_MATCHING_DEVICE:
                show_error(
                    self,
                    tr("ProfileEditor", "Invalid Components"),
                    tr("ProfileEditor", "Your Profile contains an invalid "
                       f"Component: {0} has invalid Pins that do not match "
                       "those of its device. Please delete and recreate that "
                       "component.").format(info['component_name']),
                )

    def new_component(self) -> None:
        dialog = ComponentCreator(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                selected = dialog.componentsTree.selectedItems()[0]
            except IndexError:
                return
            name = selected.toolTip(0)
            # Yes, we're using tooltips to store the full device name :)
            try:
                device = find_device(name)
            except ValueError:
                show_error(
                    self,
                    tr("ProfileEditor", "Unimplemented Component"),
                    tr("ProfileEditor", "The selected Component is currently "
                       "not implemented. Visit our GitHub to open an issue or "
                       "watch the state of development.")
                )
                return
            num_pins = len(device.PINS)
            self.profile.components.append(
                Component.new(device, [0] * num_pins, self.daemon.queue_write)
            )
            self.setup_components()

    def _set_auto_activate_param(
        self, name: str, value: int | float | bool | str
    ) -> None:
        self.profile.auto_activate_params[name] = value

    def set_auto_activate(self, text: str, init: bool = False) -> None:
        """
        Setup the layout to configure the auto-activater selected in the
        combo box.

        :param text: The name of the auto-activation manager
        :type text: str
        :param init: Wether this is the initial setup, meaning the previous
        config values should be used.
        :type init: bool
        """
        if text == self.profile.auto_activate_manager and not init:
            return
        self.profile.auto_activate_manager = text
        for widget in self.activate_config_widgets:
            self.autoActivateConfigLayout.removeWidget(widget)
        self.activate_config_widgets.clear()
        if text in (
            (tr("ProfileEditor", "Default"), tr("ProfileEditor", "Off"))
        ):
            if text == tr("ProfileEditor", "Default"):
                self.profile.auto_activate_manager = True
            else:
                self.profile.auto_activate_manager = False
            self.profile.auto_activate_params = {}
            return
        params = auto_activaters.ACTIVATERS[text][1]
        if not init:
            self.profile.auto_activate_params = {}
        for name, type in params.items():
            if type == int:
                widget = QSpinBox()
                widget.setRange(-100000, 100000)
                widget.setValue(self.profile.auto_activate_params.get(name, 0))
                widget.valueChanged.connect(
                    partial(self._set_auto_activate_param, name)
                )
            elif type == float:
                widget = QDoubleSpinBox()
                widget.setRange(-100000, 100000)
                widget.setValue(
                    self.profile.auto_activate_params.get(name, 0.0)
                )
                widget.valueChanged.connect(
                    partial(self._set_auto_activate_param, name)
                )
            elif type == bool:
                widget = QCheckBox()
                widget.setChecked(
                    self.profile.auto_activate_params.get(name, False)
                )
                widget.stateChanged.connect(
                    partial(self._set_auto_activate_param, name)
                )
            else:
                widget = QLineEdit()
                widget.setText(
                    self.profile.auto_activate_params.get(name, "")
                )
                widget.textChanged.connect(
                    partial(self._set_auto_activate_param, name)
                )
            font = widget.font()
            font.setPointSize(14)
            widget.setFont(font)
            self.activate_config_widgets.append(widget)
            self.autoActivateConfigLayout.addWidget(widget)


class ComponentCreator(QDialog, Ui_CreateComponent):  # type: ignore[misc]
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setupUi(self)

    def setupUi(self, *args: Any, **kwargs: Any) -> None:
        super().setupUi(*args, **kwargs)


class ComponentEditor(QDialog, Ui_ComponentEditor):  # type: ignore[misc]
    def __init__(self, parent: QWidget, component: Component) -> None:
        super().__init__(parent)
        self.component = component
        self.entry_hbox: dict[str, QHBoxLayout] = {}
        self.setupUi(self)

    def setupUi(self, *args: Any, **kwargs: Any) -> None:
        super().setupUi(*args, **kwargs)
        self.componentDisplay.setText(self.component.device.NAME)
        lb = self.leftVBox
        rb = self.rightVBox

        for name, num in self.component.pins.items():
            pin_hbox = QHBoxLayout()
            if name:
                pin_label = QLabel(tr("ComponentEditor", "Pin ({0}):").format(
                    name
                ))
            else:
                pin_label = QLabel(tr("ComponentEditor", "Pin:"))
            font = pin_label.font()
            font.setPointSize(14)
            pin_label.setFont(font)
            pin_spin = QSpinBox()
            font = pin_spin.font()
            font.setPointSize(14)
            pin_spin.setFont(font)
            pin_spin.setMinimum(0)
            pin_spin.setMaximum(999)
            pin_spin.setValue(num)
            pin_spin.valueChanged.connect(partial(self.pin_changed, name))
            pin_hbox.addWidget(pin_label)
            pin_hbox.addWidget(pin_spin)
            lb.addLayout(pin_hbox)

        for property, info in self.component.device.CONFIG.items():
            label = QLabel(property)
            font = label.font()
            font.setPointSize(14)
            label.setFont(font)
            default: int | float | bool | str = info["default"]  # type: ignore[assignment]  # noqa E501
            type_: type[int] | type[float] | type[bool] | type[str] = info["type"]  # type: ignore[assignment]  # noqa E501
            value = self.component.properties.get(property)
            if not isinstance(value, type_):
                value = None
            if not isinstance(default, type_):
                config.log(
                    f"Default value for property {property} has type "
                    f"{type_(default)} (should be {type_})", "WARNING",
                )
                default = type_()
            if type_ == int:
                widget = QSpinBox()
                widget.setRange(info.get("min") or 0, info.get("max") or 999999)  # type: ignore[arg-type]  # noqa E501
                widget.setValue(value if value is not None else default)  # type: ignore[arg-type]  # noqa E501
                widget.valueChanged.connect(
                    partial(self.property_changed, property)
                )
            elif type_ == float:
                widget = QDoubleSpinBox()
                widget.setRange(info.get("min") or 0.0, info.get("max") or 999999.0)  # type: ignore[arg-type]  # noqa E501
                widget.setValue(value if value is not None else default)  # type: ignore[arg-type]  # noqa E501
                widget.valueChanged.connect(
                    partial(self.property_changed, property)
                )
            elif type_ == bool:
                widget = QCheckBox()
                widget.setChecked(bool(value) if value is not None else default)  # type: ignore[arg-type]  # noqa E501
                widget.stateChanged.connect(
                    partial(self.property_changed, property)
                )
            else:
                widget = QLineEdit()
                widget.setText(value if value is not None else default)  # type: ignore[arg-type]  # noqa E501
                widget.textChanged.connect(
                    partial(self.property_changed, property)
                )
            font = widget.font()
            font.setPointSize(14)
            widget.setFont(font)
            property_hbox = QHBoxLayout()
            property_hbox.addWidget(label)
            property_hbox.addWidget(widget)
            lb.addLayout(property_hbox)

        lb.addSpacerItem(QSpacerItem(
            1, 1, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding,
        ))
        lb.addSpacerItem(QSpacerItem(
            1, 1, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed,
        ))

        tags_label = QLabel(tr("ComponentCreator", "Tags: {0}").format(
            ", ".join(self.component.device.TAGS)
        ))
        font = tags_label.font()
        font.setPointSize(14)
        tags_label.setFont(font)
        rb.addWidget(tags_label)

        def _add_signal_slot_entry(
            entry: str, actions: list[type[SignalOrSlot]], type_: str,
        ) -> None:
            # NOTE Example ButtonRow:
            # The available_signals() method may return the same signal
            # multiple times.
            label = QLabel(entry)
            font = label.font()
            font.setPointSize(14)
            label.setFont(font)
            combo = QComboBox()
            font = combo.font()
            font.setPointSize(14)
            combo.setFont(font)
            if type_ == "signal":
                combo.currentTextChanged.connect(partial(
                    self.signal_changed, entry
                ))
                if (d := self.component.signals_actions.get(entry)):
                    selected = d.get("name")
                else:
                    selected = None
            elif type_ == "slot":
                combo.currentTextChanged.connect(partial(
                    self.slot_changed, entry
                ))
                if (d := self.component.slots_actions.get(entry)):
                    selected = d.get("name")
                else:
                    selected = None
            else:
                combo.currentTextChanged.connect(self.manager_changed)
                selected = self.component.manager.get(entry)

            selected_ss: str | None = None
            combo.blockSignals(True)
            for i, signal_slot in enumerate([a.NAME for a in actions]):
                combo.addItem(signal_slot)
                if selected == signal_slot:
                    combo.setCurrentIndex(i)
                    selected_ss = signal_slot
            combo.blockSignals(False)

            property_hbox = QHBoxLayout()
            property_hbox.addWidget(label)
            property_hbox.addWidget(combo)
            self.entry_hbox[entry] = property_hbox
            rb.addLayout(property_hbox)
            if selected_ss:
                self.update_signal_slot_params(
                    entry, find_signal_slot(selected_ss), type_, property_hbox
                )

        for dig_sig in self.component.device.available_signals_digital(
            self.component.properties
        ):
            tags = [Tag.INPUT, Tag.DIGITAL]
            actions = query_signals_slots(tags, False)
            _add_signal_slot_entry(
                dig_sig, actions, "signal"
            )

        for ana_sig in self.component.device.available_signals_analog(
            self.component.properties
        ):
            tags = [Tag.INPUT, Tag.ANALOG]
            actions = query_signals_slots(tags, False)
            _add_signal_slot_entry(
                ana_sig, actions, "signal"
            )

        for dig_slo in self.component.device.available_slots_digital(
            self.component.properties
        ):
            tags = [Tag.OUTPUT, Tag.DIGITAL]
            actions = query_signals_slots(tags, False)
            _add_signal_slot_entry(dig_slo, actions, "slot")

        for ana_slo in self.component.device.available_slots_digital(
            self.component.properties
        ):
            tags = [Tag.OUTPUT, Tag.ANALOG]
            actions = query_signals_slots(tags, False)
            _add_signal_slot_entry(ana_slo, actions, "slot")

        if (actions := query_by_device(self.component.device.NAME)):
            _add_signal_slot_entry(
                tr("ComponentEditor", "Manager:"),
                actions, "manager",
            )

        rb.addSpacerItem(QSpacerItem(
            1, 1, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding,
        ))
        rb.addSpacerItem(QSpacerItem(
            1, 1, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed,
        ))

    def pin_changed(self, name: str, num: int) -> None:
        self.component.pins[name] = num

    def property_changed(
        self, property: str, value: int | float | bool | str,
    ) -> None:
        self.component.properties[property] = value

    def signal_changed(self, entry: str, value: str) -> None:
        # Params don't need to be preserved as the signal just changed
        self.component.signals_actions[entry] = {"name": value}
        self.update_signal_slot_params(
            entry, find_signal_slot(value), "signal", self.entry_hbox[entry]
        )

    def slot_changed(self, entry: str, value: str) -> None:
        # Params don't need to be preserved as the slot just changed
        self.component.slots_actions[entry] = {"name": value}
        self.update_signal_slot_params(
            entry, find_signal_slot(value), "slot", self.entry_hbox[entry]
        )

    def manager_changed(self, value: str) -> None:
        # Params don't need to be preserved as the manager just changed
        self.component.manager = {"name": value}
        self.update_signal_slot_params(
            "manager", find_signal_slot(value),
            "manager", self.entry_hbox["manager"]
        )

    def update_signal_slot_params(
        self,
        entry: str,
        signal_slot: type[SignalOrSlot],
        type_: str,
        hbox: QHBoxLayout,
    ) -> None:
        for i in reversed(range(hbox.count())[2:]):
            child = hbox.takeAt(i)
            if child and (w := child.widget()):
                w.deleteLater()
        for param in signal_slot.PARAMS:
            value = None
            if type_ == "signal":
                if (d := self.component.signals_actions.get(entry)):
                    if isinstance((p := d.get("params")), dict):
                        value = p.get(param.name)
            elif type_ == "slot":
                if (d := self.component.slots_actions.get(entry)):
                    if isinstance((p := d.get("params")), dict):
                        value = p.get(param.name)
            else:
                if isinstance(
                    (e := self.component.manager.get("params")), dict
                ):
                    value = e.get(param.name)
            if param.type == int:
                widget = QSpinBox()
                widget.setRange(param.info.get("min") or 0, param.info.get("max") or 999999)  # type: ignore[arg-type]  # noqa E501
                widget.setValue(value if value is not None else param.default)  # type: ignore[arg-type]  # noqa E501
                widget.valueChanged.connect(
                    partial(
                        self.param_changed, type_, entry, param.name
                    )
                )
            if param.type == float:
                widget = QDoubleSpinBox()
                widget.setRange(param.info.get("min") or 0.0, param.info.get("max") or 999999.0)  # type: ignore[arg-type]  # noqa E501
                widget.setValue(value if value is not None else param.default)  # type: ignore[arg-type]  # noqa E501
                widget.valueChanged.connect(
                    partial(
                        self.param_changed, type_, entry, param.name
                    )
                )
            if param.type == bool:
                widget = QCheckBox()
                widget.setChecked(bool(value) if value is not None else param.default)  # type: ignore[arg-type]  # noqa E501
                widget.stateChanged.connect(
                    partial(
                        self.param_changed, type_, entry, param.name
                    )
                )
            else:
                widget = QLineEdit()
                widget.setText(value if value is not None else param.default)  # type: ignore[arg-type]  # noqa E501
                widget.textChanged.connect(
                    partial(
                        self.param_changed, type_, entry, param.name
                    )
                )
            font = widget.font()
            font.setPointSize(14)
            widget.setFont(font)
            hbox.addWidget(widget)

    def param_changed(
        self,
        type_: str,
        entry: str,
        param: str,
        value: int | float | bool | str,
    ) -> None:
        if type_ == "signal":
            d = self.component.signals_actions.get(entry)
            if d:
                p = d.get("params")
                if isinstance(p, dict):
                    p[param] = value
                else:
                    d["params"] = {param: value}
            else:
                raise ValueError(
                    f"Entry {entry} param changed but entry doesn't exist"
                )
        elif type_ == "slot":
            d = self.component.slots_actions.get(entry)
            if d:
                p = d.get("params")
                if isinstance(p, dict):
                    p[param] = value
                else:
                    d["params"] = {param: value}
            else:
                raise ValueError(
                    f"Entry {entry} param changed but entry doesn't exist"
                )
        else:
            e = self.component.manager.get("params")
            if isinstance(e, dict):
                e[param] = value
            else:
                self.component.manager["params"] = {param: value}


class MacroEditor(QDialog, Ui_MacroEditor):  # type: ignore[misc]
    def __init__(self, parent: QWidget, macros: list[config.MACRO]) -> None:
        super().__init__(parent)
        self.macros = macros
        self.cur_macro: config.MACRO | None = None
        self.macros_items: list[tuple[config.MACRO, QListWidgetItem]] = []
        self.actions_items: list[tuple[
            config.MACRO_ACTION, QListWidgetItem
        ]] = []
        self.setupUi(self)
        self.connectSignalsSlots()

    def setupUi(self, *args: Any, **kwargs: Any) -> None:
        super().setupUi(*args, **kwargs)

        def _mousePressEvent(e: QMouseEvent) -> None:
            super(QListWidget, self.actionList).mousePressEvent(e)  # type: ignore[misc]  # noqa
            if not self.actionList.indexAt(e.pos()).isValid():
                self.actionList.clearSelection()

        self.actionList.mousePressEvent = _mousePressEvent

        self.updateUi()

    def updateUi(self) -> None:
        self.macroList.clear()
        for macro in self.macros:
            item = QListWidgetItem(macro["name"])  # type: ignore[arg-type]
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.macros_items.append((macro, item))
            self.macroList.addItem(item)
        self.actionList.clear()
        self._set_enabled_actions(False)

    def _set_enabled_actions(self, enabled: bool = True) -> None:
        self.actionList.setEnabled(enabled)
        self.editActionBtn.setEnabled(enabled)
        self.deleteActionBtn.setEnabled(enabled)
        self.untilReleasedRadio.setEnabled(enabled)
        self.untilPressedRadio.setEnabled(enabled)
        self.runTimesRadio.setEnabled(enabled)
        self.runTimesSpin.setEnabled(enabled)
        self.actionCombo.setEnabled(enabled)

    def connectSignalsSlots(self) -> None:
        self.macroList.itemSelectionChanged.connect(self.macro_list_selection)
        self.macroList.itemChanged.connect(self.rename_macro)
        self.newBtn.pressed.connect(self.new_macro)
        self.deleteBtn.pressed.connect(self.del_macro)
        self.editActionBtn.pressed.connect(self.change_action)
        self.deleteActionBtn.pressed.connect(self.delete_action)
        self.untilReleasedRadio.pressed.connect(self.mode_until_released)
        self.untilPressedRadio.pressed.connect(self.mode_until_pressed)
        self.runTimesRadio.pressed.connect(self.mode_n_times)
        self.runTimesSpin.valueChanged.connect(self.update_n_times)
        self.actionCombo.currentTextChanged.connect(self.insert_action)

    def insert_action(self) -> None:
        try:
            sel_index: QModelIndex | None = (
                self.actionList.selectedIndexes()[0]
            )
        except IndexError:
            sel_index = None

        if self.cur_macro is None:
            return

        what = self.actionCombo.currentIndex()
        value: str | int | None
        if what == 0:  # Default
            return
        if what == 1:  # Press Key
            type = "press_key"
            value = ""
        elif what == 2:  # Release Key
            type = "release_key"
            value = ""
        elif what == 3:  # Delay
            type = "delay"
            value = 50
        elif what == 4:  # Left Mouse Button Down
            type = "left_mouse_button_down"
            value = None
        elif what == 5:  # Left Mouse Button Up
            type = "left_mouse_button_up"
            value = None
        elif what == 6:  # Middle Mouse Button Down
            type = "middle_mouse_button_down"
            value = None
        elif what == 7:  # Middle Mouse Button Up
            type = "middle_mouse_button_up"
            value = None
        elif what == 8:  # Right Mouse Button Down
            type = "right_mouse_button_down"
            value = None
        elif what == 9:  # Right Mouse Button Up
            type = "right_mouse_button_up"
            value = None
        elif what == 10:  # Scroll Up
            type = "scroll_up"
            value = 1
        elif what == 11:  # Scroll Down
            type = "scroll_down"
            value = 1
        elif what == 12:  # Type Text
            type = "type_text"
            value = ""
        action: config.MACRO_ACTION = {
            "type": type,
            "value": value,
        }
        item = QListWidgetItem(self._action_to_str(action))
        if sel_index:
            idx = sel_index.row()
            self.actions_items.insert(idx, (action, item))
            self.actionList.insertItem(idx, item)
            self.cur_macro["actions"].insert(idx, action)  # type: ignore[union-attr]  # noqa
        else:
            self.actions_items.append((action, item))
            self.actionList.addItem(item)
            self.cur_macro["actions"].append(action)  # type: ignore[union-attr]  # noqa
        self.actionCombo.setCurrentIndex(0)

    def _action_tr(self, type_: str) -> str:
        match type_:
            case "press_key":
                name = tr("MacroEditor", "Press Key")
            case "release_key":
                name = tr("MacroEditor", "Release Key")
            case "delay":
                name = tr("MacroEditor", "Delay")
            case "left_mouse_button_down":
                name = tr("MacroEditor", "Left Mouse Button Down")
            case "left_mouse_button_up":
                name = tr("MacroEditor", "Left Mouse Button Up")
            case "middle_mouse_button_down":
                name = tr("MacroEditor", "Middle Mouse Button Down")
            case "middle_mouse_button_up":
                name = tr("MacroEditor", "Middle Mouse Button Up")
            case "right_mouse_button_down":
                name = tr("MacroEditor", "Right Mouse Button Down")
            case "right_mouse_button_up":
                name = tr("MacroEditor", "Right Mouse Button Up")
            case "scroll_up":
                name = tr("MacroEditor", "Scroll Up")
            case "scroll_down":
                name = tr("MacroEditor", "Scroll Down")
            case "type_text":
                name = tr("MacroEditor", "Type Text")
            case _:
                name = ""
        return name

    def _action_to_str(self, action: config.MACRO_ACTION) -> str:
        name = self._action_tr(action["type"])  # type: ignore[arg-type]

        if action["type"] in (
            "press_key", "release_key", "delay", "type_text"
        ):
            name = tr("MacroEditor", "{0}: {1}").format(name, action["value"])
        elif action["type"] in ("scroll_up", "scroll_down"):
            name = tr(
                "MacroEditor", "{0}: {1} times"
            ).format(name, action["value"])
        elif action["type"] == "delay":
            name = tr("MacroEditor", "{0}ms").format(name)
        return name

    def update_n_times(self) -> None:
        self.runTimesRadio.setChecked(True)
        self.untilReleasedRadio.setChecked(False)
        self.untilPressedRadio.setChecked(False)
        self.mode_n_times()

    def mode_n_times(self) -> None:
        if self.cur_macro is None:
            return
        self.cur_macro["mode"] = self.runTimesSpin.value()

    def mode_until_pressed(self) -> None:
        if self.cur_macro is None:
            return
        self.cur_macro["mode"] = "until_pressed_again"
        self.runTimesSpin.setValue(0)

    def mode_until_released(self) -> None:
        if self.cur_macro is None:
            return
        self.cur_macro["mode"] = "until_released"
        self.runTimesSpin.setValue(0)

    def delete_action(self) -> None:
        try:
            selected = self.actionList.selectedItems()[0]
        except IndexError:
            return
        if self.cur_macro is None:
            return
        for i, (action, item) in enumerate(self.actions_items):
            if item == selected:
                for j, macro_action in enumerate(self.cur_macro["actions"]):  # type: ignore[arg-type]  # noqa
                    if action is macro_action:
                        del self.cur_macro["actions"][j]  # type: ignore[union-attr]  # noqa
                del self.actions_items[i]
                break
        self.actionList.removeItemWidget(selected)
        self.macro_list_selection()

    def reorder_actions(self) -> None:
        if not self.cur_macro:
            return
        new_actions_items: list[
            tuple[config.MACRO_ACTION, QListWidgetItem]
        ] = []
        for item in [
            self.actionList.item(x) for x in range(self.actionList.count())
        ]:
            for action_, item_ in self.actions_items:
                if item == item_:
                    new_actions_items.append((action_, item_))
        self.actions_items = new_actions_items
        self.cur_macro["actions"] = [i[0] for i in self.actions_items]

    def macro_list_selection(self) -> None:
        try:
            selected = self.macroList.selectedItems()[0]
        except IndexError:
            return
        self.reorder_actions()
        cur_macro: config.MACRO | None = None
        for macro, item in self.macros_items:
            if selected == item:
                cur_macro = macro
        if cur_macro is None:
            return
        self.cur_macro = cur_macro
        self._set_enabled_actions(True)
        self.actionList.clear()
        self.actions_items.clear()
        for action in cur_macro["actions"]:  # type: ignore[union-attr]
            item = QListWidgetItem(self._action_to_str(action))  # type: ignore[arg-type]  # noqa
            self.actions_items.append((action, item))  # type: ignore[arg-type]
            self.actionList.addItem(item)
        self.untilReleasedRadio.blockSignals(True)
        self.untilPressedRadio.blockSignals(True)
        self.runTimesRadio.blockSignals(True)
        self.runTimesSpin.blockSignals(True)
        if cur_macro["mode"] == "until_released":
            self.untilPressedRadio.setChecked(False)
            self.runTimesRadio.setChecked(False)
            self.runTimesSpin.setValue(0)
            self.untilReleasedRadio.setChecked(True)
        elif cur_macro["mode"] == "until_pressed_again":
            self.runTimesRadio.setChecked(False)
            self.runTimesSpin.setValue(0)
            self.untilReleasedRadio.setChecked(False)
            self.untilPressedRadio.setChecked(True)
        elif isinstance(cur_macro["mode"], int):
            self.untilPressedRadio.setChecked(False)
            self.untilReleasedRadio.setChecked(True)
            self.runTimesRadio.setChecked(True)
            self.runTimesSpin.setValue(cur_macro["mode"])
        self.untilReleasedRadio.blockSignals(False)
        self.untilPressedRadio.blockSignals(False)
        self.runTimesRadio.blockSignals(False)
        self.runTimesSpin.blockSignals(False)

    def change_action(self) -> None:
        try:
            selected = self.actionList.selectedItems()[0]
        except IndexError:
            return
        cur_action: config.MACRO_ACTION | None = None
        for action, item in self.actions_items:
            if item == selected:
                cur_action = action
        if cur_action is None:
            return

        mode: Literal["delay", "scroll", "key", "text"]
        if cur_action["type"] == "delay":
            mode = "delay"
        elif cur_action["type"] in ("scroll_up", "scroll_down"):
            mode = "scroll"
        elif cur_action["type"] in ("press_key", "release_key"):
            mode = "key"
        elif cur_action["type"] == "type_text":
            mode = "text"
        else:
            return
        translation = self._action_tr(cur_action["type"])  # type: ignore[arg-type]  # noqa
        dialog = MacroActionEditor(
            self, mode, translation, cur_action["value"]  # type: ignore[arg-type]  # noqa
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            value = dialog.value
            if mode == "key" and isinstance(value, str):
                try:
                    value.encode("utf-8")
                except UnicodeEncodeError:
                    config.log("Invalid shortcut configured", "ERROR")
                    show_error(
                        self, tr("MacroEditor", "Invalid Character"),
                        tr("MacroEditor", "You entered an invalid character "
                           "in the shortcuts menu. This commonly happens when "
                           "using alternate graphics (AltGr). Please do not "
                           "use these characters.")
                    )
                    return
            cur_action["value"] = value
            self._refresh_action_list_names()

    def _refresh_action_list_names(self) -> None:
        for action, item in self.actions_items:
            item.setText(self._action_to_str(action))

    def del_macro(self) -> None:
        try:
            selected = self.macroList.selectedItems()[0]
        except IndexError:
            return
        for i, (cur_macro, item) in enumerate(self.macros_items):
            if item == selected:
                for j, macro in enumerate(self.macros):
                    if cur_macro is macro:
                        del self.macros[j]
                del self.macros_items[i]
                break
        self.macroList.removeItemWidget(selected)
        self.cur_macro = None
        self.updateUi()
        self._set_enabled_actions(False)

    def new_macro(self) -> None:
        macro: config.MACRO = {
            "name": "New Macro",
            "mode": 1,
            "actions": [],
        }
        self.macros.append(macro)
        item = QListWidgetItem(macro["name"])  # type: ignore[arg-type]
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.macroList.addItem(item)
        self.macros_items.append((macro, item))

    def rename_macro(self, selected: QListWidgetItem) -> None:
        for macro, item in self.macros_items:
            if item == selected:
                macro["name"] = selected.text()


class MacroActionEditor(QDialog, Ui_MacroActionEditor):  # type: ignore[misc]
    def __init__(
        self,
        parent: QWidget,
        mode: str,
        translation: str,
        value: str | int,
    ) -> None:
        super().__init__(parent)
        self.mode = mode
        self.translation = translation
        self.value = value

        self.widget: QWidget | None = None
        self.mod_combo: QComboBox | None = None

        self.setupUi(self)

    def setupUi(self, *args: Any, **kwargs: Any) -> None:
        super().setupUi(*args, **kwargs)

        box = self.contentHBox
        label = QLabel(self.translation)
        font = label.font()
        font.setPointSize(14)
        label.setFont(font)
        box.addWidget(label)

        if self.mode == "delay":
            if not isinstance(self.value, int):
                self.value = 0
            widget = QSpinBox()
            widget.setMinimum(0)
            widget.setMaximum(999999)
            widget.setValue(self.value)
            widget.valueChanged.connect(self.spin_value_changed)
        elif self.mode == "key":
            if not isinstance(self.value, str):
                self.value = ""
            combo = QComboBox()
            combo.addItem(tr("MacroActionEditor", "Shortcut"))
            for mod in MODS:
                combo.addItem(mod)
            font = combo.font()
            font.setPointSize(14)
            combo.setFont(font)
            combo.currentIndexChanged.connect(self.mod_combo_changed)
            self.mod_combo = combo
            box.addWidget(combo)
            widget = QKeySequenceEdit(self.value)
            widget.keySequenceChanged.connect(self.key_value_changed)
        elif self.mode == "scroll":
            if not isinstance(self.value, int):
                self.value = 0
            widget = QSpinBox()
            widget.setMinimum(1)
            widget.setMaximum(9999)
            widget.setValue(self.value)
            widget.valueChanged.connect(self.spin_value_changed)
        else:
            if not isinstance(self.value, str):
                self.value = ""
            widget = QLineEdit(self.value)
            widget.textChanged.connect(self.text_value_changed)

        font = widget.font()
        font.setPointSize(14)
        widget.setFont(font)
        box.addWidget(widget)
        self.widget = widget

    def spin_value_changed(self, value: int) -> None:
        self.value = value

    def key_value_changed(self, value: QKeySequence) -> None:
        self.value = value.toString()

    def text_value_changed(self, value: str) -> None:
        self.value = value

    def mod_combo_changed(self, value: int) -> None:
        if value == 0:
            if self.widget:
                self.widget.setEnabled(True)
                widget: QKeySequenceEdit = self.widget
                self.key_value_changed(widget.keySequence())
        else:
            if self.widget:
                self.widget.setEnabled(False)
                if not isinstance(self.mod_combo, QComboBox):
                    return
                self.value = self.mod_combo.currentText()


def launch_gui(daemon: Daemon) -> tuple[QApplication, Microstation]:
    app = QApplication(sys.argv)
    app.setApplicationName(
        tr("Microstation", "Microstation")
    )
    app.setApplicationDisplayName(
        tr("Microstation", "Microstation")
    )
    font = app.font()
    font.setFamily("Liberation Sans")
    app.setFont(font)
    langs_dir = Path(__file__).resolve().parent / "langs"
    locales: list[QLocale] = []
    translators: dict[str, QTranslator] = {}
    for file in langs_dir.iterdir():
        if file.suffix == ".qm":
            locale_name = file.stem.split("_", 1)[1]
            locale_ = QLocale(locale_name)
            locales.append(locale_)
            translator = QTranslator(app)
            translator.load(str(file))
            translators[locale_name] = translator

    default = config.get_config_value("locale")
    if default not in [i.name() for i in locales]:
        default = "en_US"
        config.set_config_value("locale", default)

    win = Microstation(daemon, locales, translators)
    return app, win
