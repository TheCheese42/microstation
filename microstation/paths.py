import platform
from pathlib import Path

from PyQt6.QtCore import QStandardPaths

ROOT_PATH = Path(__file__).parent
if "__compiled__" in globals():
    # With nuitka, __file__ will show the file in a subfolder that doesn't
    # exist.
    # With nuitka: microstation.dist/microstation/paths.py
    # Actual: microstation.dist/paths.py
    # That's why we go back another folder using .parent twice.
    ROOT_PATH = Path(__file__).parent.parent
VERSION_PATH = ROOT_PATH / "version.txt"
STYLES_PATH = ROOT_PATH / "external_styles"
ICONS_PATH = ROOT_PATH / "icons"
LANGS_PATH = ROOT_PATH / "langs"
ARDUINO_SKETCH_PATH = ROOT_PATH / "arduino"
LICENSES_PATH = ROOT_PATH / "licenses"
LICENSE_PATH = LICENSES_PATH / "LICENSE.html"
WINDOWS_LICENSE_PATH = LICENSES_PATH / "OPEN_SOURCE_LICENSES_WINDOWS.html"
LINUX_LICENSE_PATH = LICENSES_PATH / "OPEN_SOURCE_LICENSES_LINUX.html"

CONFIG_DIR = Path(
    QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
) / "Microstation"

if platform.system() == "Windows":
    LIB_DIR = Path(
        QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppLocalDataLocation
        )
    ) / "Microstation" / "lib"
else:
    LIB_DIR = Path(
        QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.HomeLocation
        )
    ) / ".microstation" / "lib"
CONFIG_PATH = CONFIG_DIR / "config.json"
LOGGER_PATH = CONFIG_DIR / "latest.log"
MC_DEBUG_LOG_PATH = CONFIG_DIR / "mcdebug.log"
SER_HISTORY_PATH = CONFIG_DIR / "serial_history.log"
PROFILES_PATH = CONFIG_DIR / "profiles.json"
MACROS_PATH = CONFIG_DIR / "macros.json"
ARDUINO_SKETCH_FORMATTED_PATH = CONFIG_DIR / "arduino"
