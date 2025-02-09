import platform
import sys
import time
import webbrowser
from collections.abc import Callable
from copy import deepcopy
from functools import partial
from pathlib import Path
from subprocess import getoutput
from threading import Thread
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

from . import config, utils
from .actions import auto_activaters
from .actions.signals_slots import (SignalOrSlot, find_signal_slot,
                                    query_by_device, query_signals_slots)
from .daemon import Daemon
from .enums import Issue, Tag
from .model import (MODS, Component, Profile, find_device, gen_profile_id,
                    validate_components)
from .paths import (ARDUINO_SKETCH_FORMATTED_PATH, ARDUINO_SKETCH_PATH,
                    ICONS_PATH, LANGS_PATH, LOGGER_PATH, MC_DEBUG_LOG_PATH,
                    SER_HISTORY_PATH, STYLES_PATH)
from .utils import get_device_info
from .version import __version__, version_string

try:
    from .ui.about_ui import Ui_About
    from .ui.component_editor_ui import Ui_ComponentEditor
    from .ui.create_component_ui import Ui_CreateComponent
    from .ui.install_boards_ui import Ui_InstallBoards
    from .ui.licenses_ui import Ui_Licenses
    from .ui.macro_action_editor_ui import Ui_MacroActionEditor
    from .ui.macro_editor_ui import Ui_MacroEditor
    from .ui.microcontroller_settings_ui import Ui_MicrocontrollerSettings
    from .ui.profile_editor_ui import Ui_ProfileEditor
    from .ui.profiles_ui import Ui_Profiles
    from .ui.serial_monitor_ui import Ui_SerialMonitor
    from .ui.settings_ui import Ui_Settings
    from .ui.welcome_ui import Ui_Welcome
    from .ui.window_ui import Ui_Microstation
except ImportError:
    config.log(
        "Failed to load UI. Did you forget to run the compile-ui script?",
        "ERROR",
    )
    sys.exit(1)

try:
    from .external_styles.breeze import breeze_pyqt6 as _
except ImportError:
    config.log(
        "Failed to load breeze styles. Did you forget to run the "
        "compile-styles script?"
        "WARNING",
    )

try:
    from .icons import resource as _  # noqa: 401
except ImportError:
    config.log(
        "Failed to load icons. Did you forget to run the compile-icons "
        "script?"
        "WARNING",
    )


tr = QApplication.translate


def translation_for_ss(ss: str) -> str:
    """
    Retrieve the translation for a signal or slot.

    :param ss: The name of the signal or slot
    :type ss: str
    :return: The translated string, if available. Else the original name.
    :rtype: str
    """
    match ss:
        case "digital_changed":
            return tr("SignalsSlots", "digital_changed")
        case "digital_high":
            return tr("SignalsSlots", "digital_high")
        case "digital_low":
            return tr("SignalsSlots", "digital_low")
        case "trigger_digital_high":
            return tr("SignalsSlots", "trigger_digital_high")
        case "trigger_digital_low":
            return tr("SignalsSlots", "trigger_digital_low")
        case "value_digital":
            return tr("SignalsSlots", "value_digital")
        case "analog_changed":
            return tr("SignalsSlots", "analog_changed")
        case "value_analog":
            return tr("SignalsSlots", "value_analog")
        case "encoder_rotated":
            return tr("SignalsSlots", "encoder_rotated")
        case "encoder_rotated_left":
            return tr("SignalsSlots", "encoder_rotated_left")
        case "encoder_rotated_right":
            return tr("SignalsSlots", "encoder_rotated_right")
        case "sw_changed":
            return tr("SignalsSlots", "sw_changed")
        case "sw_high":
            return tr("SignalsSlots", "sw_high")
        case "sw_low":
            return tr("SignalsSlots", "sw_low")
        case _:
            return ss


def show_error(parent: QWidget, title: str, desc: str) -> int:
    messagebox = QMessageBox(parent)
    messagebox.setIcon(QMessageBox.Icon.Critical)
    messagebox.setWindowTitle(title)
    messagebox.setText(desc)
    messagebox.setStandardButtons(QMessageBox.StandardButton.Ok)
    messagebox.setDefaultButton(QMessageBox.StandardButton.Ok)
    return messagebox.exec()


def show_question(parent: QWidget, title: str, desc: str) -> int:
    messagebox = QMessageBox(parent)
    messagebox.setIcon(QMessageBox.Icon.Question)
    messagebox.setWindowTitle(title)
    messagebox.setText(desc)
    messagebox.setStandardButtons(
        QMessageBox.StandardButton.No | QMessageBox.StandardButton.Yes
    )
    messagebox.setDefaultButton(QMessageBox.StandardButton.Yes)
    return messagebox.exec()


def show_info(parent: QWidget, title: str, desc: str) -> None:
    messagebox = QMessageBox(parent)
    messagebox.setIcon(QMessageBox.Icon.Information)
    messagebox.setWindowTitle(title)
    messagebox.setText(desc)
    messagebox.setStandardButtons(QMessageBox.StandardButton.Ok)
    messagebox.setDefaultButton(QMessageBox.StandardButton.Ok)
    messagebox.exec()


def ask_install_arduino_cli(parent: QWidget) -> None:
    if show_question(
        parent, tr("Microstation", "Install arduino-cli"),
        tr("Microstation", "Microstation depends on arduino-cli to "
            "interact with Microcontrollers. Should we install arduino-cli "
            "for you?"),
    ) == QMessageBox.StandardButton.Yes:
        try:
            config.log("Installing arduino-cli")
            utils.install_arduino_cli()
        except RuntimeError as e:
            config.log(f"Installing Microstation failed: {e}", "ERROR")
            show_error(
                parent, tr("Microstation", "Install failed"),
                tr("Microstation", f"An error occurred while installing: {e}")
            )
            return
        config.log("Success installing arduino-cli")
        show_info(parent, tr("Microstation", "Success"),
                  tr("Microstation",
                     "arduino-cli was installed successfully."))


class Microstation(QMainWindow, Ui_Microstation):  # type: ignore[misc]
    def __init__(
        self,
        daemon: Daemon,
        locales: list[QLocale],
        translators: dict[str, QTranslator],
        quit_callback: Callable[[], None],
    ) -> None:
        super().__init__(None)
        self.daemon = daemon
        self.locales = locales
        self.translators = translators
        self.current_translator: QTranslator | None = None
        self.quit_callback = quit_callback

        self.selected_port: str = config.get_config_value("default_port")
        self._previous_comports: list[str] = []
        self._previous_profiles: list[str] = []
        self.selected_profile: Profile | None = None
        self.quit_requested = False

        self.serial_monitor_from_index = 0
        self.ignore_version_mismatch = False

        self.setupUi(self)
        self.connectSignalsSlots()

        if config.get_config_value("show_welcome_popup"):
            self.open_welcome()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(500)

        self.quit_timer = QTimer(self)
        self.quit_timer.timeout.connect(self.check_quit_requested)
        self.quit_timer.start(100)

    def refresh(self) -> None:
        self.update_ports()
        self.mcDisplay.setText(
            self.daemon.device.name or tr("Microstation", "Not connected")
        )

        self.selected_profile = self.daemon.profile

        # To avoid disabling autodetection
        is_autodetection_enabled = self.autoActivateCheck.isChecked()
        self.update_profile_combo()
        if (
            self.selected_profile
            and self.profileCombo.currentText() != self.selected_profile.name
        ):
            self.profileCombo.setCurrentText(self.selected_profile.name)
        self.autoActivateCheck.setChecked(is_autodetection_enabled)

        if self.daemon.mc_version and not self.ignore_version_mismatch:
            mc_version_tuple = tuple(
                map(int, self.daemon.mc_version.split("."))
            )
            if (
                __version__[0] != mc_version_tuple[0]
                or __version__[1] != mc_version_tuple[1]
            ):
                self.ignore_version_mismatch = True
                if show_question(
                    self, tr("Microstation", "Version Mismatch"),
                    tr("Microstation", "The Microcontroller runs a Sketch "
                       "compiled by a previous version of Microstation. It "
                       "is recommended to upload the newest code to ensure "
                       "full functionality.\n\nDo you wish to upload the "
                       "newest code?")
                ) == QMessageBox.StandardButton.Yes:
                    self.upload_code()

    def update_profile_combo(self) -> None:
        profiles = [profile.name for profile in config.PROFILES]
        if profiles == self._previous_profiles:
            return
        self._previous_profiles = profiles
        self.profileCombo.clear()
        self.profileCombo.addItem(tr("Microstation", "No Profile"))
        for i, profile in enumerate(profiles):
            self.profileCombo.addItem(profile)
            if self.selected_profile and self.selected_profile.name == profile:
                self.profileCombo.setCurrentIndex(i)

    def update_ports(self, force: bool = False) -> None:
        try:
            current_comports = [port.device for port in comports()]
        except ValueError:
            return
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
        self.autoActivateCheck.setChecked(
            config.get_config_value("auto_detect_profiles")
        )
        self.refresh()

        # Language menu
        self.menuLanguage.clear()
        for locale_ in sorted(self.locales, key=lambda x: x.language().name):
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

        self.actionUploadCode.triggered.connect(self.upload_code)
        self.actionInstallAdditionalBoards.triggered.connect(
            self.install_boards
        )
        self.actionSettingsMC.triggered.connect(self.open_mc_settings)

        self.actionSerialMonitor.triggered.connect(self.open_serial_monitor)
        self.actionLog.triggered.connect(self.open_log)
        self.actionSerialLog.triggered.connect(self.open_serial_log)
        self.actionExportSerialHistory.triggered.connect(
            self.export_serial_history
        )

        self.actionThemeDefault.triggered.connect(self.set_default_style)

        self.actionOpenWiki.triggered.connect(self.open_wiki)

        self.actionAboutMicrostation.triggered.connect(self.open_about)
        self.actionOpenGitHub.triggered.connect(self.open_github)
        self.actionOpenSourceLicenses.triggered.connect(self.open_licenses)

        self.profileCombo.currentTextChanged.connect(self.set_profile)
        self.autoActivateCheck.stateChanged.connect(self.set_auto_activate)

    def open_welcome(self) -> None:
        dialog = Welcome(self, self.open_wiki, self.open_github)
        dialog.exec()
        config.set_config_value(
            "show_welcome_popup", not dialog.doNotShowAgainCheck.isChecked()
        )

    def open_wiki(self) -> None:
        self.open_url("https://github.com/TheCheese42/microstation/wiki")

    def open_github(self) -> None:
        self.open_url("https://github.com/TheCheese42/microstation")

    def open_licenses(self) -> None:
        dialog = Licenses(self, self.open_url)
        dialog.exec()

    def set_profile(self, profile_name: str) -> None:
        for profile in config.PROFILES:
            if profile.name == profile_name:
                self.daemon.set_profile(profile)
                config.set_config_value("auto_detect_profiles", False)
                self.autoActivateCheck.setChecked(False)
                self.daemon.set_auto_activation_enabled(False)
                break
        else:
            self.daemon.set_profile(None)
            self.autoActivateCheck.setChecked(False)
            self.daemon.set_auto_activation_enabled(False)

    def set_auto_activate(self, state: bool) -> None:
        self.daemon.set_auto_activation_enabled(state)
        config.set_config_value("auto_detect_profiles", state)

    def upload_code(self) -> None:
        port = self.daemon.port
        code = (ARDUINO_SKETCH_PATH / "arduino.ino").read_text("utf-8")
        try:
            cli_information = utils.lookup_arduino_cli_information()
            code = utils.format_string(
                code,
                core=utils.core_from_fqbn(fqbn := utils.lookup_fqbn(port)),
                board=fqbn,
                microstation_version=version_string,
                arduino_cli_version=cli_information.version,
                arduino_cli_commit=cli_information.commit,
                arduino_cli_date=cli_information.date,
                baudrate=f"{config.get_config_value("baudrate")}",
            )
            ARDUINO_SKETCH_FORMATTED_PATH.mkdir(exist_ok=True)
            with open(
                ARDUINO_SKETCH_FORMATTED_PATH / "arduino.ino",
                "w", encoding="utf-8"
            ) as fp:
                fp.write(code)
            config.log(f"Uploading sketch to port {port} with device "
                       f"{self.daemon.device}")
            utils.upload_code(port, str(ARDUINO_SKETCH_FORMATTED_PATH))
        except utils.MissingArduinoCLIError:
            ask_install_arduino_cli(self)
            return
        except RuntimeError as e:
            config.log(f"Uploading sketch failed: {e}", "ERROR")
            show_error(
                self, tr("Microstation", "Error uploading"),
                tr("Microstation", "Uploading failed: {0}"
                   "\n\nMake sure your board is connected and the correct port"
                   " is selected.").format(str(e))
            )
            return
        config.log(f"Success uploading sketch to port {port} with device "
                   f"{self.daemon.device}")
        show_info(self, tr("Microstation", "Success"),
                  tr("Microstation", "The code was uploaded successfully."))

    def install_boards(self) -> None:
        dialog = InstallBoards(self)
        dialog.exec()

    def open_mc_settings(self) -> None:
        dialog = MicrocontrollerSettings(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            something_changed = False
            max_adc_value = dialog.adcSpin.value()
            prev_max_adc_value = config.get_config_value("max_adc_value")
            if max_adc_value != prev_max_adc_value:
                something_changed = True
            config.set_config_value("max_adc_value", max_adc_value)

            if something_changed:
                if show_question(
                    self, tr("Microstation", "Upload updated code"),
                    tr("Microstation", "Your settings were updated "
                       "successfully. To apply them to your Microcontroller, "
                       "you need to upload the newly generated code. You can "
                       "do this here or under \"Microcontroller\" -> "
                       "\"Upload Code\".\n\nUpload the new code?")
                ) == QMessageBox.StandardButton.Yes:
                    self.upload_code()

    def open_serial_monitor(self) -> None:
        dialog = SerialMonitor(
            self, self.daemon, self.serial_monitor_from_index
        )
        dialog.exec()
        self.serial_monitor_from_index = dialog.from_index
        self.daemon.received_task_callbacks.remove(dialog.queue_new_task)

    def open_log(self) -> None:
        self.open_file(LOGGER_PATH)

    def open_serial_log(self) -> None:
        self.open_file(MC_DEBUG_LOG_PATH)

    def export_serial_history(self) -> None:
        SER_HISTORY_PATH.write_text(
            "\n".join(self.daemon.full_history), "utf-8",
        )
        self.open_file(SER_HISTORY_PATH)

    def open_about(self) -> None:
        dialog = About(self)
        dialog.exec()

    def open_url(self, url: str) -> None:
        thread = Thread(target=self._open_url_threaded, args=(url,))
        config.log(f"Opening url {url} in thread {thread.name}", "DEBUG")
        thread.start()

    def _open_url_threaded(self, url: str) -> None:
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
        thread = Thread(target=self._open_file_threaded, args=(path,))
        config.log(f"Opening file at path {path} in thread {thread.name}",
                   "DEBUG")
        thread.start()

    def _open_file_threaded(self, path: str | Path) -> None:
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
            self.autoActivateCheck.setChecked(auto_detect_profiles)
            self.daemon.set_auto_activation_enabled(auto_detect_profiles)
            hide_to_tray_startup = dialog.hideToTrayCheck.isChecked()
            config.set_config_value(
                "hide_to_tray_startup", hide_to_tray_startup
            )

    def open_profiles(self) -> None:
        dialog = Profiles(
            self, deepcopy(config.PROFILES), self.daemon, self.open_wiki
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config.PROFILES = dialog.profiles
            config.save_profiles(config.PROFILES)
            self.selected_profile = None
            self.refresh()
            if dialog.modified_profiles:
                self.daemon.queue_restart()

    def open_macros(self) -> None:
        dialog = MacroEditor(self, deepcopy(config.MACROS))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dialog.reorder_actions()
            config.MACROS = dialog.macros
            config.save_macros(config.MACROS)

    def set_paused(self) -> None:
        paused = self.actionPause.isChecked()
        if paused:
            config.log("Pausing the daemon", "DEBUG")
        else:
            config.log("Unpausing the daemon", "DEBUG")
        self.daemon.set_paused(paused)
        self.actionPause.setText(
            tr("Microstation", "Resume")
            if paused
            else tr("Microstation", "Pause")
        )

    def set_style(self, path: Path, full_name: str) -> None:
        config.set_config_value("theme", full_name)
        stylesheet = path.read_text("utf-8")
        self.setStyleSheet(stylesheet)

    def set_default_style(self) -> None:
        config.set_config_value("theme", "")
        self.setStyleSheet("")

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
        self.quit_callback()

    def request_quit(self) -> None:
        self.quit_requested = True

    def check_quit_requested(self) -> None:
        if self.quit_requested:
            super().close()
            self.quit_callback()


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
        self,
        parent: QWidget,
        profiles: list[Profile],
        daemon: Daemon,
        open_wiki_method: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.profiles = profiles
        self.daemon = daemon
        self.open_wiki_method = open_wiki_method
        self.modified_profiles: list[Profile] = []
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
        self.buttonBox.accepted.connect(self.accept_received)

    def accept_received(self) -> None:
        names = [p.name for p in self.profiles]
        if len(names) != len(set(names)):
            config.log(
                "Cancelled Profiles Dialog accept signal because of duplicated"
                " Profile names.", "INFO"
            )
            show_error(self, tr("Profiles", "Duplicated Profile Names"),
                       tr("Profiles", "Some Profiles have the same name. "
                          "All Profiles deserve their own names, don't they?"))
        else:
            self.accept()

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
            self,
            deepcopy(self.profiles[selected]),
            self.daemon,
            self.open_wiki_method,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_profile = dialog.profile
            new_profile.name = dialog.nameEdit.text()
            new_profile.auto_activate_priority = dialog.prioritySpin.value()
            self.profiles[selected] = new_profile
            self.updateProfileList()
            self.modified_profiles.append(new_profile)

    def delete_profile(self) -> None:
        try:
            selected = self.profilesList.selectedIndexes()[0].row()
        except IndexError:
            return
        if show_question(
            self, tr("Profiles", "Delete Profile"),
            tr("Profiles", "Do you really want to delete the Profile "
               f"{self.profilesList.currentItem().text()}?")
        ) == QMessageBox.StandardButton.Yes:
            self.profiles.pop(selected)
            self.updateProfileList()


class ProfileEditor(QDialog, Ui_ProfileEditor):  # type: ignore[misc]
    def __init__(
        self,
        parent: QWidget,
        profile: Profile,
        daemon: Daemon,
        open_wiki_method: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.profile = profile
        self.daemon = daemon
        self.open_wiki_method = open_wiki_method
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
            edit_btn.setToolTip(
                tr("ProfileEditor", "Edit this Component")
            )
            edit_font = edit_btn.font()
            edit_font.setPointSize(14)
            edit_btn.setFont(edit_font)
            edit_btn.clicked.connect(partial(self.edit_component, i))
            rest_hbox.addWidget(edit_btn)
            delete_btn = QPushButton(tr("ProfileEditor", "Delete"))
            delete_btn.setToolTip(
                tr("ProfileEditor", "Delete this Component")
            )
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
        dialog = ComponentEditor(
            self, deepcopy(component), self.open_wiki_method
        )
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
                config.log(
                    "Cancelled ProfileEditor Dialog accept signal because of "
                    "duplicated pins.", "INFO"
                )
                show_error(
                    self,
                    tr("ProfileEditor", "Invalid Components"),
                    tr("ProfileEditor", "Your Profile contains invalid "
                       f"Components: Pin {0} was used multiple "
                       "times.").format(info['pin']),
                )
                return
            case Issue.COMPONENT_PINS_NOT_MATCHING_DEVICE:
                config.log(
                    "Cancelled ProfileEditor Dialog accept signal because "
                    f"component {info['component_name']} has an invalid "
                    "pinout", "INFO"
                )
                show_error(
                    self,
                    tr("ProfileEditor", "Invalid Components"),
                    tr("ProfileEditor", "Your Profile contains an invalid "
                       "Component: {0} has invalid Pins that do not match "
                       "those of its device. Please delete and recreate that "
                       "component.").format(info['component_name']),
                )
                return

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
                config.log(f"User selected unimplemented Component {name}",
                           "INFO")
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
    def __init__(
        self,
        parent: QWidget,
        component: Component,
        open_wiki_method: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.component = component
        self.open_wiki_method = open_wiki_method
        self.entry_hbox: dict[str, QHBoxLayout] = {}
        self.setupUi(self)
        self.connectSignalsSlots()

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
            label = QLabel(str(info.get("translation", property)))
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
            if tt := info.get("tooltip"):
                if isinstance(tt, str):
                    label.setToolTip(tt)
                    widget.setToolTip(tt)
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
            label = QLabel(translation_for_ss(entry))
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

        for ana_slo in self.component.device.available_slots_analog(
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

    def connectSignalsSlots(self) -> None:
        self.wikiBtn.clicked.connect(self.open_wiki_method)

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
            elif param.type == float:
                widget = QDoubleSpinBox()
                widget.setRange(param.info.get("min") or 0.0, param.info.get("max") or 999999.0)  # type: ignore[arg-type]  # noqa E501
                widget.setValue(value if value is not None else param.default)  # type: ignore[arg-type]  # noqa E501
                widget.valueChanged.connect(
                    partial(
                        self.param_changed, type_, entry, param.name
                    )
                )
            elif param.type == bool:
                widget = QCheckBox()
                widget.setChecked(bool(value) if value is not None else param.default)  # type: ignore[arg-type]  # noqa E501
                widget.stateChanged.connect(
                    partial(
                        self.param_changed, type_, entry, param.name
                    )
                )
            elif param.type == QKeySequence:
                widget = QKeySequenceEdit()
                widget.setKeySequence(value if value is not None else param.default)  # type: ignore[arg-type]  # noqa E501
                widget.keySequenceChanged.connect(
                    partial(
                        self.param_changed, type_, entry, param.name
                    )
                )
            elif param.type == "macro":
                widget = QComboBox()
                for i, macro in enumerate(config.MACROS):
                    widget.addItem(macro["name"])  # type: ignore[arg-type]
                    if macro["name"] == value:
                        widget.setCurrentIndex(i)
                self.param_changed(
                    type_, entry, param.name, value
                    if isinstance(value, str) else widget.currentText()
                )
                widget.currentTextChanged.connect(
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
        value: int | float | bool | str | QKeySequence,
    ) -> None:
        if isinstance(value, QKeySequence):
            value = value.toString()
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
        self.buttonBox.accepted.connect(self.accept_requested)

    def accept_requested(self) -> None:
        macro_names = [macro["name"] for macro in self.macros]
        if len(macro_names) != len(set(macro_names)):
            config.log("Cancelling MacroEditor Accept Signal because of "
                       "duplicated names", "INFO")
            show_error(self, tr("MacroEditor", "Duplicated Macro Names"),
                       tr("MacroEditor", "Some Macros have the same name. "
                          "All Macros deserve their own names, don't they?"))
        else:
            self.accept()

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
                    config.log("Invalid shortcut configured", "INFO")
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
            widget.setToolTip(
                tr("MacroActionEditor", "Set a delay in Milliseconds")
            )
            widget.setMinimum(0)
            widget.setMaximum(999999)
            widget.setValue(self.value)
            widget.valueChanged.connect(self.spin_value_changed)
        elif self.mode == "key":
            if not isinstance(self.value, str):
                self.value = ""
            combo = QComboBox()
            combo.setToolTip(
                tr("MacroActionEditor",
                   "Select a modifier key or define a custom shortcut")
            )
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
            widget.setToolTip(
                tr("MacroActionEditor", "Select a Key Sequence to execute")
            )
            widget.keySequenceChanged.connect(self.key_value_changed)
        elif self.mode == "scroll":
            if not isinstance(self.value, int):
                self.value = 0
            widget = QSpinBox()
            widget.setToolTip(
                tr("MacroActionEditor", "Set the number of scrolls to perform")
            )
            widget.setMinimum(1)
            widget.setMaximum(9999)
            widget.setValue(self.value)
            widget.valueChanged.connect(self.spin_value_changed)
        else:
            if not isinstance(self.value, str):
                self.value = ""
            widget = QLineEdit(self.value)
            widget.setToolTip(
                tr("MacroActionEditor", "Set a text to type")
            )
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


class InstallBoards(QDialog, Ui_InstallBoards):  # type: ignore[misc]
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.cores_items: list[tuple[str, QListWidgetItem]] = []
        self.install_job_time = 0.0
        self.install_job_thread: Thread | None = None
        self.timer: QTimer | None = None
        self.install_job_error_args: tuple[str, str] | None = None
        self.setupUi(self)
        self.connectSignalsSlots()

    def setupUi(self, *args: Any, **kwargs: Any) -> None:
        super().setupUi(*args, **kwargs)
        self.updateUi()
        if "breeze" in config.get_config_value("theme").lower():
            self.progressHBox.insertSpacerItem(0, QSpacerItem(
                20, 1, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed,
            ))

    def updateUi(self) -> None:
        try:
            config.log("Fetching available cores")
            boards = list(utils.available_cores())
        except utils.MissingArduinoCLIError:
            ask_install_arduino_cli(self)
            QTimer.singleShot(0, self.close)
            return
        except RuntimeError as e:
            config.log(f"Error fetching list of Arduino Cores: {e}", "ERROR")
            show_error(
                self, tr("InstallBoards", "Error fetching Boards"), str(e)
            )
            QTimer.singleShot(0, self.close)
            return
        self.boardsList.clear()
        self.cores_items.clear()
        for name, installed, core in boards:
            text = tr("InstallBoards", "{name} ({core})").format(
                name=name, core=core
            )
            if installed:
                text += tr("InstallBoards", " [{0}]").format(
                    tr("InstallBoards", "Installed")
                )
            item = QListWidgetItem(text)
            self.boardsList.addItem(item)
            self.cores_items.append((core, item))

    def connectSignalsSlots(self) -> None:
        self.installBtn.clicked.connect(partial(
            self.start_install_job, self.install_selected
        ))
        self.removeBtn.clicked.connect(partial(
            self.start_install_job, self.remove_selected
        ))

    def install_selected(self, selected: QListWidgetItem) -> None:
        for core, item in self.cores_items:
            if item == selected:
                try:
                    config.log(f"Installing core {core}")
                    utils.install_core(core)
                except utils.MissingArduinoCLIError:
                    ask_install_arduino_cli(self)
                    QTimer.singleShot(0, self.close)
                    return
                except RuntimeError as e:
                    config.log(f"Error installing Arduino Core {core}: {e}",
                               "ERROR")
                    self.install_job_error_args = (
                        tr("InstallBoards", "Error installing"), str(e)
                    )
                    return

    def remove_selected(self, selected: QListWidgetItem) -> None:
        for core, item in self.cores_items:
            if item == selected:
                try:
                    config.log(f"Removing core {core}")
                    utils.remove_core(core)
                except utils.MissingArduinoCLIError:
                    ask_install_arduino_cli(self)
                    QTimer.singleShot(0, self.close)
                    return
                except RuntimeError as e:
                    config.log(f"Error removing Arduino Core {core}: {e}",
                               "ERROR")
                    self.install_job_error_args = (
                        tr("InstallBoards", "Error removing"), str(e)
                    )
                    return

    def start_install_job(
        self, job: Callable[[QListWidgetItem], None]
    ) -> None:
        if self.install_job_thread:
            config.log("User tried to start an install job, but one is running"
                       " already!", "INFO")
            show_error(
                self, tr("InstallBoards", "Already installing"),
                tr("InstallBoards", "An install or remove job is already "
                   "running.")
            )
            return
        try:
            selected = self.boardsList.selectedItems()[0]
        except IndexError:
            return
        self.install_job_thread = Thread(target=job, args=(selected,))
        self.install_job_thread.start()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_progress_bar)
        self.timer.start(5)
        self.install_job_time = time.time()

    def update_progress_bar(self) -> None:
        if (
            not self.install_job_thread
            or not self.install_job_thread.is_alive()
        ):
            self.install_job_thread = None
            self.install_job_time = 0
            if self.install_job_error_args:
                show_error(self, *self.install_job_error_args)
            else:
                config.log("Core install job succeeded", "INFO")
            self.install_job_error_args = None
            if self.timer:
                self.timer.stop()
                self.timer = None
            self.progressBar.setValue(0)
            self.updateUi()
            return
        progress, ltr = utils.progress_bar_animation_snappy(
            time.time() - self.install_job_time
        )
        self.progressBar.setLayoutDirection(
            Qt.LayoutDirection.LeftToRight if ltr
            else Qt.LayoutDirection.RightToLeft
        )
        self.progressBar.setValue(progress)

class MicrocontrollerSettings(QDialog, Ui_MicrocontrollerSettings):  # type: ignore[misc]  # noqa
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setupUi(self)
        self.connectSignalsSlots()

    def setupUi(self, *args: Any, **kwargs: Any) -> None:
        super().setupUi(*args, **kwargs)
        self.adcSpin.setValue(config.get_config_value("max_adc_value"))

    def connectSignalsSlots(self) -> None:
        self.buttonBox.accepted.connect(self.accept_requested)

    def accept_requested(self) -> None:
        adc_value = self.adcSpin.value()
        for i in range(21):
            if adc_value == 2 ** i:
                self.accept()
                break
        else:
            show_error(
                self, tr("MicrocontrollerSettings",  "Invalid ADC Value"),
                tr("MicrocontrollerSettings", "You maximum ADC value is "
                   "invalid. Only powers of 2 are allowed, else the input "
                   "values of analog components will be wrong. "
                   "Microcontrollers always use powers of 2 for their maximum "
                   "ADC value.\n\nCommon example values:\n - 1024 (Most "
                   "Arduino Boards)\n - 4096 (esp32 Boards)")
            )


class SerialMonitor(QDialog, Ui_SerialMonitor):  # type: ignore[misc]
    def __init__(
        self, parent: QWidget, daemon: Daemon, from_index: int
    ) -> None:
        super().__init__(parent)
        self.daemon = daemon
        self.from_index = from_index
        self.setupUi(self)
        self.connectSignalsSlots()
        self.daemon.received_task_callbacks.append(self.queue_new_task)

    def setupUi(self, *args: Any, **kwargs: Any) -> None:
        super().setupUi(*args, **kwargs)
        self.update_text()

    def update_text(self) -> None:
        try:
            self.textBrowser.setPlainText(
                "\n".join(self.daemon.in_history[self.from_index:])
            )
        except IndexError:
            self.textBrowser.setPlainText("")
        self.textBrowser.verticalScrollBar().setValue(
            self.textBrowser.verticalScrollBar().maximum()
        )

    def queue_new_task(self, task: str) -> None:
        QTimer.singleShot(0, partial(self.new_task, task))

    def new_task(self, task: str) -> None:
        self.textBrowser.append(task)
        if config.get_config_value("autoscroll_serial_monitor"):
            self.textBrowser.verticalScrollBar().setValue(
                self.textBrowser.verticalScrollBar().maximum()
            )

    def connectSignalsSlots(self) -> None:
        self.enterBtn.clicked.connect(self.send_command)
        self.clearBtn.clicked.connect(self.clear_history)
        self.autoscrollCheck.checkStateChanged.connect(self.autoscroll_changed)

    def send_command(self) -> None:
        text = self.cmdLine.text()
        if not text:
            return
        self.cmdLine.clear()
        self.daemon.queue_write(text)

    def clear_history(self) -> None:
        self.from_index += len(self.textBrowser.toPlainText().splitlines()) + 1
        self.update_text()

    def autoscroll_changed(self) -> None:
        state = self.autoscrollCheck.isChecked()
        config.set_config_value("autoscroll_serial_monitor", state)


class About(QDialog, Ui_About):  # type: ignore[misc]
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setupUi(self)

    def setupUi(self, *args: Any, **kwargs: Any) -> None:
        super().setupUi(*args, **kwargs)
        self.versionDisplay.setText(version_string)


class Licenses(QDialog, Ui_Licenses):  # type: ignore[misc]
    def __init__(
        self, parent: QWidget, open_url_method: Callable[[str], None]
    ) -> None:
        super().__init__(parent)
        self.open_url = open_url_method
        self.names_urls_licenses: dict[str, tuple[str, str]] = {}
        self.setupUi(self)
        self.connectSignalsSlots()

    def setupUi(self, *args: Any, **kwargs: Any) -> None:
        super().setupUi(*args, **kwargs)
        for i in range(self.list.count()):
            item = self.list.item(i)
            # Don't question this practice
            license_text = item.toolTip()
            url = item.statusTip()
            item.setToolTip(
                tr("Licenses", "{url} (double tap to open)").format(
                    url=url
                )
            )
            item.setStatusTip("")
            self.names_urls_licenses[item.text()] = (url, license_text)

    def connectSignalsSlots(self) -> None:
        self.list.itemSelectionChanged.connect(self.show_license)
        self.list.itemDoubleClicked.connect(self.double_clicked)

    def show_license(self) -> None:
        try:
            selected = self.list.selectedItems()[0]
        except IndexError:
            return
        self.browser.setText(self.names_urls_licenses[selected.text()][1])

    def double_clicked(self, item: QListWidgetItem) -> None:
        self.open_url(self.names_urls_licenses[item.text()][0])


class Welcome(QDialog, Ui_Welcome):  # type: ignore[misc]
    def __init__(
        self, parent: QWidget,
        open_wiki_method: Callable[[], None],
        open_github_method: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.setupUi(self)
        self.open_wiki_method = open_wiki_method
        self.open_github_method = open_github_method
        self.connectSignalsSlots()

    def setupUi(self, *args: Any, **kwargs: Any) -> None:
        super().setupUi(*args, **kwargs)
        self.doNotShowAgainCheck.setChecked(
            not config.get_config_value("show_welcome_popup")
        )

    def connectSignalsSlots(self) -> None:
        self.wikiBtn.clicked.connect(self.open_wiki_method)
        self.githubBtn.clicked.connect(self.open_github_method)
        self.closeBtn.clicked.connect(self.close)


def launch_gui(
    daemon: Daemon, quit_callback: Callable[[], None],
) -> tuple[QApplication, Microstation]:
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
    locales: list[QLocale] = []
    translators: dict[str, QTranslator] = {}
    for file in sorted(LANGS_PATH.iterdir()):
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

    win = Microstation(daemon, locales, translators, quit_callback)
    return app, win
