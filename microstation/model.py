# from abc import ABCMeta, abstractmethod
from enum import StrEnum
from functools import cache
from importlib import import_module
from typing import Any, Callable, Literal

try:
    from .paths import DEVICES_PATH
except ImportError:
    from paths import DEVICES_PATH  # type: ignore[no-redef]


type COMPONENT = dict[str, Any]
type PROFILE = dict[str, Any]


@cache
def fetch_devices() -> list[type["Device"]]:
    devices: list[type["Device"]] = []
    for file in DEVICES_PATH.iterdir():
        if file.suffix == ".py":
            try:
                module = import_module(f".devices.{file.stem}")
            except ImportError:
                module = import_module(f"devices.{file.stem}")
            for device_type in module.__all__:
                device = getattr(module, device_type)
                devices.append(device)
    return devices


@cache
def find_device(name: str) -> type["Device"]:
    for device in fetch_devices():
        if device.NAME == name:
            return device
    raise ValueError(f"Device {name} not found")


class Profile:
    def __init__(self, data: PROFILE, write_method: Callable[[str], None]):
        self.write_method = write_method
        self.name = data["name"]
        self.auto_activate_priority = data["auto_activate_priority"]
        self.components = [
            Component(i, write_method) for i in data["components"]
        ]


class Component:
    def __init__(self, data: COMPONENT, write_method: Callable[[str], None]):
        self.write_method = write_method
        device = data["device"]
        self.device = find_device(device)
        self.pins: list[int] = data["pins"]
        self.properties: dict[str, Any] = data["properties"]
        self.slots: dict[str, list[str]] = data["slots"]

    def emit_signal(self, signal: str, *args: Any) -> None:
        for slot in getattr(self, signal, []):
            getattr(self.device, slot)(*args)

    def control_pin(self, pin_name: str, pin_number: int, value: int) -> None:
        for pin in self.device.PINS:
            if pin.name == pin_name:
                type = pin.type
                io_type = pin.io_type
                if io_type != "output":
                    raise RuntimeError(f"Pin {pin_name} is not an output pin")
                self.write_method(f"WRITE {type.upper()} {pin_number} {value}")


class Pin:
    def __init__(
        self,
        type: Literal["analog", "digital", "both"],
        io_type: Literal["input", "output"],
        name: str = "",
        properties: list[str] | None = None,
    ):
        self.type = type
        self.io_type = io_type
        self.name = name
        if properties is None:
            self.properties: list[str] = []


class Tag(StrEnum):
    INPUT = "input"
    OUTPUT = "output"
    ANALOG = "analog"
    DIGITAL = "digital"
    CONVERTER = "converter"
    MANAGER = "manager"


class Device:  # (ABCMeta):
    NAME = "Device"
    TAGS: list[Tag] = []
    PINS: list[Pin] = []
