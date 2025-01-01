import sys
from functools import partial
from pathlib import Path

from PyQt6.QtCore import QLocale, QTranslator
from PyQt6.QtWidgets import QApplication, QMainWindow

try:
    from . import config
    from .external_styles.breeze import breeze_pyqt6 as _  # noqa: F811
    from .icons import resource as _  # noqa: F811
    from .paths import STYLES_PATH
    from .ui.window_ui import Ui_MainWindow
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
        from ui.window_ui import Ui_MainWindow
    except ImportError:
        config.log(
            "Failed to load UI. Did you forget to run the compile-ui script?"
            "ERROR",
        )
    from paths import STYLES_PATH  # type: ignore[no-redef]  # noqa: F401


class Window(QMainWindow, Ui_MainWindow):  # type: ignore[misc]
    def __init__(
        self,
        locales: list[QLocale],
        translators: dict[str, QTranslator],
    ) -> None:
        super().__init__(None)
        self.locales = locales
        self.translators = translators
        self.current_translator: QTranslator | None = None
        self.setupUi(self)
        self.connectSignalsSlots()

    def setupUi(self, window: QMainWindow) -> None:
        super().setupUi(window)
        self.setWindowTitle("Microstation")

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
        self.actionThemeDefault.triggered.connect(
            lambda: self.setStyleSheet("")
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


def launch_gui() -> tuple[QApplication, Window]:
    app = QApplication(sys.argv)
    app.setApplicationName("Microstation")
    app.setApplicationDisplayName("Microstation")
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
            translator = QTranslator()
            translator.load(str(file))
            translators[locale_name] = translator

    default = config.get_config_value("locale")
    if default not in [i.name() for i in locales]:
        default = "en_US"
        config.set_config_value("locale", default)
    # default_locale = QLocale(default)
    # QLocale.setDefault(default_locale)

    # default_translator = translators.get(default)
    # if default_translator:
    #     app.installTranslator(default_translator)

    win = Window(locales, translators)
    return app, win
