import inspect
import sys
from collections.abc import Callable
from importlib import import_module
from types import ModuleType

from . import devices
from .actions.auto_activaters import ACTIVATERS
from .actions.signals_slots import SIGNALS_SLOTS, Param, SignalOrSlot, UniStr
from .config import log
from .devices import DEVICES
from .enums import Tag
from .gui import PLUGIN_DEVICES
from .model import Component, Device, Pin
from .paths import PLUGINS_PATH

MODULES: list[ModuleType] = []


def plugin_log(
    message: str,
    level: str = "INFO",
) -> None:
    frame_records = inspect.stack()[1]
    calling_module = inspect.getmodulename(frame_records[1])
    log(f"[PLUGIN] {calling_module}: {message}", level)


def register_auto_activator(
    name: str,
    params: dict[str, type],
) -> Callable[[Callable[..., bool]], Callable[..., bool]]:
    def decorator(activator: Callable[..., bool]) -> Callable[..., bool]:
        ACTIVATERS[name] = (activator, params)
        return activator
    return decorator


def register_signal_slot(
    signal_slot: type[SignalOrSlot]
) -> type[SignalOrSlot]:
    SIGNALS_SLOTS.append(signal_slot)
    return signal_slot


def register_device(device: type[Device]) -> type[Device]:
    DEVICES.append(device.__name__)
    setattr(devices, device.__name__, device)
    PLUGIN_DEVICES.append((device.__name__, device.NAME))
    return device


def load_plugins() -> None:
    MODULES.clear()
    sys.path.append(str(PLUGINS_PATH.absolute().resolve()))
    log("Searching for plugins...", "INFO")
    plugin_count = 0
    for file in PLUGINS_PATH.iterdir():
        if file.is_dir():
            continue
        if file.suffix != ".py":
            continue
        plugin_count += 1
        try:
            module = import_module(file.stem)
            log(f"Imported plugin: {file.stem}", "INFO")
        except ImportError as e:
            log(f"Plugin file at {file.absolute()} couldn't be imported: {e}",
                "ERROR")
            continue
        MODULES.append(module)
    log(f"Loaded {len(MODULES)}/{plugin_count} plugins.", "INFO")


__all__: list[str] = [
    "Component",
    "Device",
    "load_plugins",
    "MODULES",
    "Param",
    "Pin",
    "plugin_log",
    "register_auto_activator",
    "register_device",
    "register_signal_slot",
    "SignalOrSlot",
    "Tag",
    "UniStr",
]
