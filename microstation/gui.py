import locale
import sys
from functools import partial
from pathlib import Path

from PyQt6.QtCore import QLocale, QTranslator
from PyQt6.QtWidgets import QApplication, QMainWindow

try:
    from . import config
    from .icons import resource as _
    from .paths import STYLES_PATH
    #from .styles import breeze_dark as _  # noqa: F811
    from .ui.window_ui import Ui_MainWindow
except ImportError:
    import config  # type: ignore[no-redef]
    try:
        from icons import resource as _  # noqa: F401
    except ImportError:
        config.log(
            "ERROR",
            "Failed to load icons. Did you forget to run the compile-icons "
            "script?"
        )
    # try:
    #     #from styles import breeze_dark as _  # noqa: F401, F811
    # except ImportError:
    #     config.log(
    #         "ERROR",
    #         "Failed to load styles. Did you forget to run the compile-styles "
    #         "script?"
    #     )
    try:
        from ui.window_ui import Ui_MainWindow
    except ImportError:
        config.log(
            "ERROR",
            "Failed to load UI. Did you forget to run the compile-ui script?"
        )
    from paths import STYLES_PATH  # type: ignore[no-redef]  # noqa: F401


class Window(QMainWindow, Ui_MainWindow):  # type: ignore[misc]
    def __init__(
        self, locales: list[QLocale],
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
        self.menuLanguage.clear()
        for locale_ in self.locales:
            print(locale_.name())
            action = self.menuLanguage.addAction(locale_.language().name)
            action.triggered.connect(partial(self.change_language, locale_))

    def connectSignalsSlots(self) -> None:
        self.actionThemeDefault.triggered.connect(
            lambda: self.setStyleSheet("")
        )
        self.actionThemeBreezeDark.triggered.connect(
            lambda: self.setStyleSheet(
                (STYLES_PATH / "breeze_dark.qss").read_text()
            )
        )

    def change_language(self, locale: QLocale) -> None:
        print(locale.name())
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

    os_default = locale.getdefaultlocale()[0]
    if os_default not in [i.name() for i in locales]:
        os_default = "en_US"
    default_locale = QLocale(os_default)
    QLocale.setDefault(default_locale)

    default_translator = translators.get(os_default)
    if default_translator:
        app.installTranslator(default_translator)

    win = Window(locales, translators)
    return app, win
