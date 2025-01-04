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

    def export(self) -> PROFILE:
        return {
            "name": self.name,
            "auto_activate_priority": self.auto_activate_priority,
            "components": [
                component.export() for component in self.components
            ],
        }


class Component:
    def __init__(self, data: COMPONENT, write_method: Callable[[str], None]):
        self.write_method = write_method
        device = data["device"]
        self.device = find_device(device)
        self.pins: dict[str, int] = data["pins"]  # name: number
        self.properties: dict[str, Any] = data["properties"]
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
