import json
import locale
import platform
from datetime import datetime
from typing import Any, Optional, Union

try:
    from .paths import (CONFIG_DIR, CONFIG_PATH, LOGGER_PATH, MACROS_PATH,
                        MC_DEBUG_LOG_PATH, PROFILES_PATH)
except ImportError:
    from paths import (CONFIG_DIR, CONFIG_PATH,  # type: ignore[no-redef]
                       LOGGER_PATH, MACROS_PATH, MC_DEBUG_LOG_PATH,
                       PROFILES_PATH)


DEFAULT_CONFIG = {
    "theme": "",
    "locale": locale.getdefaultlocale()[0],
    "default_port": "COM0" if platform.system() == "Windows" else "/dev/ttyS0",
    "baudrate": 9600,
    "auto_detect_profiles": True,
    "hide_to_tray_startup": True,
}

MACRO_ACTION = dict[str, Optional[Union[str, int]]]
MACRO = dict[str, Union[str, int, list[MACRO_ACTION]]]


def config_exists() -> bool:
    return CONFIG_PATH.exists()


def create_app_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def trunc_log() -> None:
    with open(LOGGER_PATH, "w") as fp:
        fp.write("")

    with open(MC_DEBUG_LOG_PATH, "w") as fp:
        fp.write("")


def ensure_profiles_file() -> None:
    if not PROFILES_PATH.exists():
        with open(PROFILES_PATH, "w", encoding="utf-8") as fp:
            fp.write("[]")


def ensure_macros_file() -> None:
    if not MACROS_PATH.exists():
        with open(MACROS_PATH, "w", encoding="utf-8") as fp:
            fp.write("[]")


def init_config() -> None:
    create_app_dir()
    trunc_log()
    ensure_profiles_file()
    ensure_macros_file()

    if not config_exists():
        with open(CONFIG_PATH, "w", encoding="utf-8") as fp:
            json.dump(DEFAULT_CONFIG, fp)


def _get_config() -> dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fp:
        conf: dict[str, Any] = json.load(fp)
    return conf


def _overwrite_config(config: dict[str, Any]) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as fp:
        json.dump(config, fp)


def get_config_value(key: str) -> Any:
    try:
        val = _get_config()[key]
    except KeyError:
        val = DEFAULT_CONFIG[key]
    return val


def set_config_value(key: str, value: Union[str, int, float, bool]) -> None:
    config = _get_config()
    config[key] = value
    _overwrite_config(config)


def get_macros() -> list[MACRO]:
    with open(MACROS_PATH, "r", encoding="utf-8") as fp:
        text: list[MACRO] = json.load(fp)
    return text


def set_macros(macros: list[MACRO]) -> None:
    with open(MACROS_PATH, "w", encoding="utf-8") as fp:
        json.dump(macros, fp)


def log(msg: str, level: str = "INFO") -> None:
    with open(LOGGER_PATH, "a", encoding="utf-8") as fp:
        fp.write(f"[{level}] [{datetime.now().isoformat()}] {msg}\n")


def log_mc(msg: str) -> None:
    with open(MC_DEBUG_LOG_PATH, "a", encoding="utf-8") as fp:
        fp.write(f"[{datetime.now().isoformat()}] {msg}\n")


class LogStream:
    def __init__(self, level: str = "INFO") -> None:
        self.level = level

    def write(self, text: str) -> None:
        log(text, self.level)
