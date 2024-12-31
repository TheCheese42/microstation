import sys
from pathlib import Path

from PyQt6.QtCore import QLocale, QTranslator
from PyQt6.QtWidgets import QApplication, QMainWindow

try:
    from .icons import resource as _
    from .ui.window_ui import Ui_MainWindow
except ImportError:
    from icons import resource as _  # noqa: F401
    from ui.window_ui import Ui_MainWindow


class Window(QMainWindow, Ui_MainWindow):  # type: ignore[misc]
    def __init__(self, locales: list[QLocale], translators: dict[str, QTranslator]) -> None:
        super().__init__(None)
        self.locales = locales
        self.translators = translators
        self.current_translator: QTranslator | None = None
        self.setupUi(self)

    def setupUi(self, window: QMainWindow) -> None:
        super().setupUi(window)
        self.setWindowTitle("Microstation")
        self.menuLanguage.clear()
        for locale in self.locales:
            action = self.menuLanguage.addAction(locale.language().name)
            action.triggered.connect(
                lambda checked, loc=locale: self.change_language(loc)
            )

    def change_language(self, locale: QLocale) -> None:
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
            locale = QLocale(locale_name)
            locales.append(locale)
            translator = QTranslator()
            translator.load(str(file))
            translators[locale_name] = translator
    
    # Set the default locale to en_US
    default_locale = QLocale("en_US")
    QLocale.setDefault(default_locale)
    
    # Load the default translator
    default_translator = translators.get("en_US")
    if default_translator:
        app.installTranslator(default_translator)
    
    win = Window(locales, translators)
    return app, win
