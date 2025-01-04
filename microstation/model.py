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
        self.id: int = data["id"]
        if not isinstance(self.id, int):
            raise ValueError(
                f"Profile id must be an int, got {type(self.id)}"
            )
        self.name: str = data["name"]
        if not isinstance(self.name, str):
            raise ValueError(
                f"Profile name must be a string, got {type(self.name)}"
            )
        self.auto_activate_priority: int = data["auto_activate_priority"]
        if not isinstance(self.auto_activate_priority, int):
            raise ValueError(
                "Profile auto_activate_priority must be an int, got "
                f"{type(self.auto_activate_priority)}"
            )
        self.auto_activate_manager: str | bool = data["auto_activate_manager"]
        if not (
            isinstance(self.auto_activate_manager, str)
            or isinstance(self.auto_activate_manager, bool)
        ):
            raise ValueError(
                "Profile auto_activate_manager must be either str or bool, "
                f"got {type(self.auto_activate_priority)}"
            )
        self.components = [
            Component(i, write_method) for i in data["components"]
        ]

    def export(self) -> PROFILE:
        return {
            "id": self.id,
            "name": self.name,
            "auto_activate_priority": self.auto_activate_priority,
            "components": [
                component.export() for component in self.components
            ],
        }

    @classmethod
    def new(cls, id: int, write_method: Callable[[str], None]) -> "Profile":
        return cls(
            {
                "id": id,
                "name": "New Profile",
                "auto_activate_priority": 0,
                "auto_activate_manager": False,
                "components": [],
            },
            write_method,
        )


def gen_profile_id(profiles: list[Profile]) -> int:
    ids: list[int] = [profile.id for profile in profiles]
    if not ids:
        return 0
    return max(ids) + 1


class Component:
    def __init__(self, data: COMPONENT, write_method: Callable[[str], None]):
        self.write_method = write_method
        self.device = find_device(data["device"])
        self.pins: dict[str, int] = data["pins"]  # name: number
        if not isinstance(self.pins, dict):
            raise ValueError(
                f"Component pins must be a dict, got {type(self.pins)}"
            )
        elif self.pins.keys() != {pin.name for pin in self.device.PINS}:
            raise ValueError(
                "Component pins must match device pins, got "
                f"{self.pins.keys()}"
            )
        elif not all([isinstance(value, int) for value in self.pins.values()]):
            raise ValueError(
                "Component pin values must be integers, got "
                f"{[type(value) for value in self.pins.values()]}"
            )
        self.properties: dict[str, Any] = data["properties"]
        if not isinstance(self.properties, dict):
            raise ValueError(
                "Component properties must be a dict, got "
                f"{type(self.properties)}"
            )

        self.callbacks: dict[str, list[Callable[...,  None]]] = {}

    def export(self) -> COMPONENT:
        return {
            "device": self.device.NAME,
            "pins": self.pins,
            "properties": self.properties,
        }

    def register_callback(
        self, signal: str, callback: Callable[..., None]
    ) -> None:
        if signal not in self.device.available_signals():
            raise ValueError(
                f"Signal {signal} not available for {self.device.NAME}"
            )
        try:
            self.callbacks[signal].append(callback)
        except KeyError:
            self.callbacks[signal] = [callback]

    def emit_signal(self, signal: str, *args: Any) -> None:
        for signal_callback in self.callbacks.get(signal, []):
            signal_callback(*args)

    def call_slot(self, slot: str, *args: Any) -> None:
        self.device.call_slot(slot, self.pins, *args)

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

    @classmethod
    def available_signals(cls) -> list[str]:
        signals = []
        if Tag.INPUT in cls.TAGS:
            if Tag.DIGITAL in cls.TAGS:
                signals.extend(
                    ["digital_changed", "digital_high", "digital_low"]
                )
            if Tag.ANALOG in cls.TAGS:
                signals.extend(["analog_changed"])
        return signals

    @classmethod
    def available_slots(cls) -> list[str]:
        slots = []
        if Tag.OUTPUT in cls.TAGS:
            if Tag.DIGITAL in cls.TAGS:
                slots.extend(["trigger_digital_high", "trigger_digital_low"])
            if Tag.ANALOG in cls.TAGS:
                slots.extend(["value_analog"])
        return slots

    @classmethod
    def call_slot(cls, slot: str, pin_data: dict[str, int], *args: Any) -> str:
        if slot not in cls.available_slots():
            raise ValueError(f"Slot {slot} not available for {cls.NAME}")
        command: str = getattr(cls, slot)(pin_data, *args)
        return command

    @classmethod
    def trigger_digital_high(cls, pin_data: dict[str, int]) -> str:
        if "trigger_digital_high" not in cls.available_slots():
            raise ValueError(
                f"Slot trigger_digital_high not available for {cls.NAME}"
            )
        pin: int | None = None
        for device_pin in cls.PINS:
            if device_pin.type == "digital" and device_pin.io_type == "output":
                pin = pin_data[device_pin.name]
                break
        if pin is None:
            raise ValueError(
                f"Device {cls.NAME} has no digital output pin to trigger"
            )
        return f"WRITE DIGITAL {pin} 1"

    @classmethod
    def trigger_digital_low(cls, pin_data: dict[str, int]) -> str:
        if "trigger_digital_low" not in cls.available_slots():
            raise ValueError(
                f"Slot trigger_digital_low not available for {cls.NAME}"
            )
        pin: int | None = None
        for device_pin in cls.PINS:
            if device_pin.type == "digital" and device_pin.io_type == "output":
                pin = pin_data[device_pin.name]
                break
        if pin is None:
            raise ValueError(
                f"Device {cls.NAME} has no digital output pin to trigger"
            )
        return f"WRITE DIGITAL {pin} 0"

    @classmethod
    def value_analog(cls, pin_data: dict[str, int], *args: int) -> str:
        if "value_analog" not in cls.available_slots():
            raise ValueError(
                f"Slot value_analog not available for {cls.NAME}"
            )
        elif (
            len(args) != 1
            or not isinstance(args[0], int)
        ):
            raise ValueError(
                "Slot value_analog requires 1 argument of type int (got "
                f"{args})"
            )
        pin: int | None = None
        for device_pin in cls.PINS:
            if device_pin.type == "analog" and device_pin.io_type == "output":
                pin = pin_data[device_pin.name]
                break
        if pin is None:
            raise ValueError(
                f"Device {cls.NAME} has no analog output pin to trigger"
            )
        return f"WRITE ANALOG {pin} {args[0]}"
