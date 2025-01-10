import sys
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QLocale, QTimer, QTranslator
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                             QDoubleSpinBox, QFrame, QHBoxLayout, QLabel,
                             QLineEdit, QMainWindow, QMessageBox, QPushButton,
                             QSizePolicy, QSpacerItem, QSpinBox, QVBoxLayout,
                             QWidget)
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
    from .model import (Component, Profile, find_device, gen_profile_id,
                        validate_components)
    from .paths import STYLES_PATH
    from .ui.component_editor_ui import Ui_ComponentEditor
    from .ui.create_component_ui import Ui_CreateComponent
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
    from model import Component  # type: ignore[no-redef]  # noqa: F401
    from model import Profile  # type: ignore[no-redef]  # noqa: F401
    from model import find_device  # type: ignore[no-redef]  # noqa: F401
    from model import gen_profile_id  # type: ignore[no-redef]  # noqa: F401
    from model import validate_components  # type: ignore[no-redef] # noqa F401
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

    def connectSignalsSlots(self) -> None:
        self.actionRefresh_Ports.triggered.connect(self.update_ports)
        self.actionRestart_Daemon.triggered.connect(self.daemon.queue_restart)
        self.actionPause.triggered.connect(self.set_paused)
        self.actionRun_in_Background.triggered.connect(self.hide)
        self.actionQuit.triggered.connect(self.full_close)

        self.actionSettings.triggered.connect(self.open_settings)
        self.actionProfiles.triggered.connect(self.open_profiles)

        self.actionThemeDefault.triggered.connect(
            lambda: self.setStyleSheet("")
        )

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
