import sys
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QLocale, QTimer, QTranslator
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QApplication, QDialog, QMainWindow, QWidget
from serial.tools.list_ports import comports

try:
    from . import config
    from .daemon import Daemon
    from .external_styles.breeze import breeze_pyqt6 as _  # noqa: F811
    from .icons import resource as _  # noqa: F811
    from .model import Profile, gen_profile_id
    from .paths import STYLES_PATH
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
        from ui.profiles_ui import Ui_Profiles
        from ui.settings_ui import Ui_Settings
        from ui.window_ui import Ui_Microstation
    except ImportError:
        config.log(
            "Failed to load UI. Did you forget to run the compile-ui script?"
            "ERROR",
        )
    from daemon import Daemon  # type: ignore[no-redef]  # noqa: F401
    from model import (Profile,  # type: ignore[no-redef]  # noqa: F401
                       gen_profile_id)
    from paths import STYLES_PATH  # type: ignore[no-redef]  # noqa: F401
    from utils import get_device_info  # type: ignore[no-redef]  # noqa: F401


tr = QApplication.translate


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
        self.setStyleSheet(path.read_text("utf-8"))

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
        dialog = ProfileEditor(self, self.profiles[selected], self.daemon)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # TODO ...
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
        self.setupUi(self)


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
