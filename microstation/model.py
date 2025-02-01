# from abc import ABCMeta, abstractmethod
from collections.abc import Callable
from functools import cache
from importlib import import_module
from typing import Any, Literal

from pynput.keyboard import Key

from .enums import Issue, Tag

try:
    from .actions.signals_slots import find_signal_slot, get_ss_instance
    from .paths import DEVICES_PATH
except ImportError:
    from actions.signals_slots import (  # type: ignore  # noqa
        find_signal_slot, get_ss_instance)
    from paths import DEVICES_PATH  # type: ignore[no-redef]


type COMPONENT = dict[str, Any]
type PROFILE = dict[str, Any]

MODS = ["Ctrl", "Shift", "Alt", "AltGr", "Tab"]
KEY_LOOKUP = {
    "Alt": Key.alt,
    "AltGr": Key.alt_gr,
    "Backspace": Key.backspace,
    "CapsLock": Key.caps_lock,
    "Ctrl": Key.ctrl,
    "Del": Key.delete,
    "Down": Key.down,
    "End": Key.end,
    "Return": Key.enter,
    "Esc": Key.esc,
    "F1": Key.f1,
    "F2": Key.f2,
    "F3": Key.f3,
    "F4": Key.f4,
    "F5": Key.f5,
    "F6": Key.f6,
    "F7": Key.f7,
    "F8": Key.f8,
    "F9": Key.f9,
    "F10": Key.f10,
    "F11": Key.f11,
    "F12": Key.f12,
    "F13": Key.f13,
    "F14": Key.f14,
    "F15": Key.f15,
    "F16": Key.f16,
    "F17": Key.f17,
    "F18": Key.f18,
    "F19": Key.f19,
    "F20": Key.f20,
    "Home Page": Key.home,
    "Ins": Key.insert,
    "Left": Key.left,
    "NumLock": Key.num_lock,
    "PgDown": Key.page_down,
    "PgUp": Key.page_up,
    "Print": Key.print_screen,
    "Right": Key.right,
    "ScrollLock": Key.scroll_lock,
    "Shift": Key.shift,
    "Space": Key.space,
    "Tab": Key.tab,
    "Up": Key.up,
}


@cache
def fetch_devices() -> list[type["Device"]]:
    devices: list[type["Device"]] = []
    for file in DEVICES_PATH.iterdir():
        if file.suffix == ".py":
            try:
                module = import_module(f".devices.{file.stem}", "microstation")
            except (ImportError, TypeError):
                module = import_module(f"microstation.devices.{file.stem}")
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
        self.auto_activate_params: dict[str, Any] = data[
            "auto_activate_params"
        ]
        if not (isinstance(self.auto_activate_params, dict)):
            raise ValueError(
                "Profile auto_activate_params must be a dict, got "
                f"{type(self.auto_activate_params)}"
            )
        self.components = [
            Component(i, write_method) for i in data["components"]
        ]

    def export(self) -> PROFILE:
        return {
            "id": self.id,
            "name": self.name,
            "auto_activate_priority": self.auto_activate_priority,
            "auto_activate_manager": self.auto_activate_manager,
            "auto_activate_params": self.auto_activate_params,
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
                "auto_activate_params": {},
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
        self.properties: dict[str, int | float | str | bool] = data[
            "properties"
        ]
        if not isinstance(self.properties, dict):
            raise ValueError(
                "Component properties must be a dict, got "
                f"{type(self.properties)}"
            )
        self.signals_actions: dict[
            str, dict[str, str | dict[str, int | float | bool | str]]
        ] = data["signals_actions"]
        if not isinstance(self.signals_actions, dict):
            raise ValueError(
                "Component signals_actions must be a dict, got "
                f"{type(self.signals_actions)}"
            )
        for k, v in self.signals_actions.items():
            if not isinstance(k, str):
                raise ValueError(
                    "Component signals_actions keys must be strings, got "
                    f"{type(k)}"
                )
            if not isinstance(v, dict):
                raise ValueError(
                    "Component signals_actions values must be a dict, got "
                    f"{type(v)}"
                )
        self.slots_actions: dict[
            str, dict[str, str | dict[str, int | float | bool | str]]
        ] = data["slots_actions"]
        if not isinstance(self.slots_actions, dict):
            raise ValueError(
                "Component slots_actions must be a dict, got "
                f"{type(self.slots_actions)}"
            )
        for k, v in self.slots_actions.items():
            if not isinstance(k, str):
                raise ValueError(
                    "Component slots_actions keys must be strings, got "
                    f"{type(k)}"
                )
            if not isinstance(v, dict):
                raise ValueError(
                    "Component slots_actions values must be a dict, got "
                    f"{type(v)}"
                )
        self.manager: dict[
            str, str | dict[str, int | float | bool | str]
        ] = data["manager"]
        if not isinstance(self.manager, dict):
            raise ValueError(
                f"Component manager must be a dict, got {type(self.manager)}"
            )
        for key, val in self.manager.items():
            if not isinstance(key, str):
                raise ValueError(
                    "Component manager keys must be strings, got "
                    f"{type(key)}"
                )
            if not isinstance(val, str):
                raise ValueError(
                    "Component manager values must be string, got "
                    f"{type(val)}"
                )

    def __str__(self) -> str:
        return f"Component with Device {self.device.NAME} on Pins {self.pins}"

    @classmethod
    def new(
        cls,
        device: type["Device"],
        pins: list[int],
        write_method: Callable[[str], None],
    ) -> "Component":
        return cls(
            {
                "device": device.NAME,
                "pins": {name: pin for name, pin in zip(
                    [p.name for p in device.PINS], pins
                )},
                "properties": {},
                "signals_actions": {},
                "slots_actions": {},
                "manager": {},
            },
            write_method,
        )

    def export(self) -> COMPONENT:
        return {
            "device": self.device.NAME,
            "pins": self.pins,
            "properties": self.properties,
            "signals_actions": self.signals_actions,
            "slots_actions": self.slots_actions,
            "manager": self.manager,
        }

    def emit_signal(self, signal: str, *args: Any) -> None:
        action = self.signals_actions.get(signal, None)
        if action:
            name = action["name"]
            if not isinstance(name, str):
                raise TypeError(
                    f"Action name for signal {signal} must be a string, got "
                    f"{type(name)}"
                )
            instance = get_ss_instance(find_signal_slot(name))
            if isinstance(action["params"], dict):
                params = action["params"].items()
                for attr, value in params:
                    setattr(instance, attr, value)
            instance.call(signal, *args)

    def call_slot(self, slot: str, *args: Any) -> None:
        self.device.call_slot(slot, self.pins, *args)

    # XXX
    # def control_pin(self, pin_name: str, pin_number: int, value: int) -> None:  # noqa XXX
    #     for pin in self.device.PINS:
    #         if pin.name == pin_name:
    #             type = pin.type
    #             io_type = pin.io_type
    #             if io_type != "output":
    #                 raise RuntimeError(f"Pin {pin_name} is not an output pin")  # noqa XXX
    #             self.write_method(f"WRITE {type.upper()} {pin_number} {value}")  # noqa XXX


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


def validate_components(
    components: list[Component]
) -> tuple[Issue, dict[str, Any]]:
    all_pins: list[int] = []
    for component in components:
        if component.pins.keys() != {
            pin.name for pin in component.device.PINS
        }:
            return (
                Issue.COMPONENT_PINS_NOT_MATCHING_DEVICE,
                {"component_name": component.device.NAME}
            )
        all_pins.extend(list(component.pins.values()))
    for pin in all_pins:
        if all_pins.count(pin) > 1:
            return Issue.DUPLICATED_PIN, {"pin": pin}
    return Issue.NONE, {}


type CONFIG_TYPE = type[int] | type[float] | type[bool] | type[str]
type CONFIG_VALUE = int | float | bool | str


class Device:  # (ABCMeta):
    NAME = "Device"
    TAGS: list[Tag] = []
    PINS: list[Pin] = []
    # Ex.: {"sensitivity": {"type": int, "default": 1, "min": 1, "max": 9999}}
    CONFIG: dict[str, dict[str, CONFIG_VALUE | CONFIG_TYPE]] = {}

    @classmethod
    def available_signals_digital(
        cls, properties: dict[str, CONFIG_VALUE] | None = None,
    ) -> list[str]:
        if Tag.INPUT in cls.TAGS and Tag.DIGITAL in cls.TAGS:
            return ["digital_changed", "digital_high", "digital_low"]
        return []

    @classmethod
    def available_signals_analog(
        cls, properties: dict[str, CONFIG_VALUE] | None = None,
    ) -> list[str]:
        if Tag.INPUT in cls.TAGS and Tag.ANALOG in cls.TAGS:
            return ["analog_changed"]
        return []

    @classmethod
    def available_signals(
        cls, properties: dict[str, CONFIG_VALUE] | None = None,
    ) -> list[str]:
        # Signal = Thing sent by input device
        return cls.available_signals_digital() + cls.available_signals_analog()

    @classmethod
    def available_slots_digital(
        cls, properties: dict[str, CONFIG_VALUE] | None = None,
    ) -> list[str]:
        if Tag.OUTPUT in cls.TAGS and Tag.DIGITAL in cls.TAGS:
            return ["trigger_digital_high", "trigger_digital_low"]
        return []

    @classmethod
    def available_slots_analog(
        cls, properties: dict[str, CONFIG_VALUE] | None = None,
    ) -> list[str]:
        if Tag.OUTPUT in cls.TAGS and Tag.ANALOG in cls.TAGS:
            return ["value_analog"]
        return []

    @classmethod
    def available_slots(
        cls, properties: dict[str, CONFIG_VALUE] | None = None,
    ) -> list[str]:
        # Slot = Command to an output device
        return cls.available_slots_digital() + cls.available_slots_analog()

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
