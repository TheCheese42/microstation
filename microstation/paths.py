from pathlib import Path

from PyQt6.QtCore import QStandardPaths

ROOT_PATH = Path(__file__).parent
STYLES_PATH = ROOT_PATH / "styles"
LICENSES_PATH = ROOT_PATH / "licenses"
LICENSE_PATH = LICENSES_PATH / "LICENSE.html"
WINDOWS_LICENSE_PATH = LICENSES_PATH / "OPEN_SOURCE_LICENSES_WINDOWS.html"
LINUX_LICENSE_PATH = LICENSES_PATH / "OPEN_SOURCE_LICENSES_LINUX.html"

CONFIG_DIR = Path(
    QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
) / "Buttonbox"
CONFIG_PATH = CONFIG_DIR / "config.json"
LOGGER_PATH = CONFIG_DIR / "latest.log"
MC_DEBUG_LOG_PATH = CONFIG_DIR / "mcdebug.log"
SER_HISTORY_PATH = CONFIG_DIR / "serial_history.log"
PROFILES_PATH = CONFIG_DIR / "profiles.json"
MACROS_PATH = CONFIG_DIR / "macros.json"
