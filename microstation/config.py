import json
import locale
import platform
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .model import Profile
from .paths import (CONFIG_DIR, CONFIG_PATH, LIB_DIR, LOGGER_PATH, MACROS_PATH,
                    MC_DEBUG_LOG_PATH, PLUGINS_PATH, PROFILES_PATH)
from .version import version_string

DEFAULT_CONFIG: dict[str, str | int | float | bool | list[str]] = {
    "show_welcome_popup": True,
    "theme": "",
    "locale": locale.getdefaultlocale()[0] or "en_US",
    "default_port": (
        "COM0" if platform.system() == "Windows"
        else "/dev/ttyACM0"
    ),
    "baudrate": 9600,
    "enable_bluetooth": False,
    "auto_detect_profiles": True,
    "hide_to_tray_startup": False,
    "board_manager_urls": [],
    "bluetooth_enabled": False,
    "autoscroll_serial_monitor": True,
    "max_adc_value": 1024,
    "max_dig_inp_pins": 50,
    "max_ana_inp_pins": 50,
    "custom_fqbn": "",
    "esp32_bluetooth_support": False,
    "ssd1306_oled_display_support": False,
    "ssd1306_oled_display_resolution_is_32px": False,
}

type MACRO_ACTION = dict[str, str | int | None]
type MACRO = dict[str, str | int | list[MACRO_ACTION]]


PROFILES: list[Profile] = []
MACROS: list[MACRO] = []


def config_exists() -> bool:
    return CONFIG_PATH.exists()


def create_app_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def create_lib_dir() -> None:
    LIB_DIR.mkdir(parents=True, exist_ok=True)


def trunc_log() -> None:
    with open(LOGGER_PATH, "w") as fp:
        fp.write("")

    with open(MC_DEBUG_LOG_PATH, "w") as fp:
        fp.write("")


def ensure_profiles_file() -> None:
    if not PROFILES_PATH.exists():
        PROFILES_PATH.write_text("[]", "utf-8")
    else:
        try:
            json.loads(PROFILES_PATH.read_text("utf-8"))
        except json.decoder.JSONDecodeError:
            PROFILES_PATH.write_text("[]", "utf-8")


def ensure_macros_file() -> None:
    if not MACROS_PATH.exists():
        MACROS_PATH.write_text("[]", "utf-8")
    else:
        try:
            json.loads(MACROS_PATH.read_text("utf-8"))
        except json.decoder.JSONDecodeError:
            MACROS_PATH.write_text("[]", "utf-8")


def init_config() -> None:
    create_app_dir()
    create_lib_dir()
    trunc_log()
    ensure_profiles_file()
    ensure_macros_file()
    PLUGINS_PATH.mkdir(parents=True, exist_ok=True)

    if not config_exists():
        with open(CONFIG_PATH, "w", encoding="utf-8") as fp:
            json.dump(DEFAULT_CONFIG, fp)


def _get_config() -> dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fp:
        text = fp.read()
    try:
        conf: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError as e:
        log(f"Failed to decode configuration file: {e}", "ERROR")
        log("Creating new config")
        conf = DEFAULT_CONFIG
    for key in conf.copy():
        if key not in DEFAULT_CONFIG:
            del conf[key]
    for key in DEFAULT_CONFIG:
        if key not in conf:
            conf[key] = DEFAULT_CONFIG[key]
    return conf


def _overwrite_config(config: dict[str, Any]) -> None:
    try:
        text = json.dumps(config)
    except Exception as e:
        log(f"Failed to dump configuration: {e}", "ERROR")
        return
    with open(CONFIG_PATH, "w", encoding="utf-8") as fp:
        fp.write(text)


def get_config_value(key: str) -> Any:
    try:
        val = _get_config()[key]
    except KeyError:
        val = DEFAULT_CONFIG[key]
    return val


def set_config_value(
    key: str, value: str | int | float | bool | list[str]
) -> None:
    config = _get_config()
    config[key] = value
    _overwrite_config(config)


def load_profiles(write_method: Callable[[str], None]) -> list[Profile]:
    with open(PROFILES_PATH, "r", encoding="utf-8") as fp:
        profiles = [Profile(data, write_method) for data in json.load(fp)]
    return profiles


def save_profiles(profiles: list[Profile]) -> None:
    with open(PROFILES_PATH, "w", encoding="utf-8") as fp:
        json.dump([profile.export() for profile in profiles], fp)


def load_macros() -> list[MACRO]:
    with open(MACROS_PATH, "r", encoding="utf-8") as fp:
        text: list[MACRO] = json.load(fp)
    return text


def save_macros(macros: list[MACRO]) -> None:
    with open(MACROS_PATH, "w", encoding="utf-8") as fp:
        json.dump(macros, fp)


def log(msg: str, level: str = "INFO") -> None:
    time = datetime.now().isoformat()
    with open(LOGGER_PATH, "a", encoding="utf-8") as fp:
        fp.write(f"[{time}] [{level}] {msg}\n")


def log_mc(msg: str) -> None:
    with open(MC_DEBUG_LOG_PATH, "a", encoding="utf-8") as fp:
        fp.write(f"[{datetime.now().isoformat()}] {msg}\n")


class LogStream:
    def __init__(self, level: str = "INFO") -> None:
        self.level = level

    def write(self, text: str) -> None:
        log(text, self.level)


def log_basic() -> None:
    log(f"Microstation - Version {version_string}")
    log(f"Running on {platform.platform()}")
