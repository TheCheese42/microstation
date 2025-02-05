# from abc import ABCMeta, abstractmethod
import random
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from functools import cache
from threading import Thread
from typing import Any, Literal

from pynput.keyboard import Controller as KController
from pynput.keyboard import Key, KeyCode
from pynput.keyboard import Listener as KListener
from pynput.mouse import Button
from pynput.mouse import Controller as MController
from pynput.mouse import Listener as MListener

try:
    from .actions.signals_slots import find_signal_slot, get_ss_instance
    from .enums import Issue, Tag
    from .paths import DEVICES_PATH
except ImportError:
    from actions.signals_slots import (  # type: ignore  # noqa
        find_signal_slot, get_ss_instance)
    from enums import Issue, Tag  # type: ignore[no-redef]
    from paths import DEVICES_PATH  # type: ignore[no-redef]


type COMPONENT = dict[str, Any]
type PROFILE = dict[str, Any]
type MACRO_ACTION = dict[str, str | int | None]
type MACRO = dict[str, str | int | list[MACRO_ACTION]]

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
    try:
        from . import devices as devices_module
    except ImportError:
        import devices as devices_module  # type: ignore[no-redef]
    for device_type in devices_module.__all__:
        device = getattr(devices_module, device_type)
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
        self.id = random.randint(100000, 999999)
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
        command = self.device.call_slot(slot, self.pins, *args)
        if command:
            self.write_method(command)


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
            return [
                "trigger_digital_high", "trigger_digital_low", "value_digital"
            ]
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
    def trigger_digital_high(
        cls, pin_data: dict[str, int], *args: bool
    ) -> str:
        if args[0] is not True:
            return ""
        if "trigger_digital_high" not in cls.available_slots():
            raise ValueError(
                f"Slot trigger_digital_high not available for {cls.NAME}"
            )
        pin: int | None = None
        for device_pin in cls.PINS:
            if (
                device_pin.type in ("digital", "both")
                and device_pin.io_type == "output"
            ):
                pin = pin_data[device_pin.name]
                break
        if pin is None:
            raise ValueError(
                f"Device {cls.NAME} has no digital output pin to trigger"
            )
        return f"WRITE DIG {pin:0>3} 1"

    @classmethod
    def trigger_digital_low(cls, pin_data: dict[str, int], *args: bool) -> str:
        if args[0] is not False:
            return ""
        if "trigger_digital_low" not in cls.available_slots():
            raise ValueError(
                f"Slot trigger_digital_low not available for {cls.NAME}"
            )
        pin: int | None = None
        for device_pin in cls.PINS:
            if (
                device_pin.type in ("digital", "both")
                and device_pin.io_type == "output"
            ):
                pin = pin_data[device_pin.name]
                break
        if pin is None:
            raise ValueError(
                f"Device {cls.NAME} has no digital output pin to trigger"
            )
        return f"WRITE DIG {pin:0>3} 0"

    @classmethod
    def value_digital(cls, pin_data: dict[str, int], *args: bool) -> str:
        if args[0] not in (True, False):
            return ""
        if "value_digital" not in cls.available_slots():
            raise ValueError(
                f"Slot value_digital not available for {cls.NAME}"
            )
        pin: int | None = None
        for device_pin in cls.PINS:
            if (
                device_pin.type in ("digital", "both")
                and device_pin.io_type == "output"
            ):
                pin = pin_data[device_pin.name]
                break
        if pin is None:
            raise ValueError(
                f"Device {cls.NAME} has no digital output pin to control"
            )
        return f"WRITE DIG {pin:0>3} {int(args[0])}"

    @classmethod
    def value_analog(cls, pin_data: dict[str, int], *args: float) -> str:
        if "value_analog" not in cls.available_slots():
            raise ValueError(
                f"Slot value_analog not available for {cls.NAME}"
            )
        elif (
            len(args) != 1
            or not isinstance(args[0], float)
        ):
            raise ValueError(
                "Slot value_analog requires 1 argument of type float (got "
                f"{args})"
            )
        pin: int | None = None
        for device_pin in cls.PINS:
            if (
                device_pin.type in ("digital", "both")
                and device_pin.io_type == "output"
            ):
                pin = pin_data[device_pin.name]
                break
        if pin is None:
            raise ValueError(
                f"Device {cls.NAME} has no analog output pin to trigger"
            )
        try:
            from .config import get_config_value
        except ImportError:
            from config import get_config_value  # type: ignore[no-redef]
        analog_adc = int(args[0] / 100.0 * get_config_value("max_adc_value"))
        return f"WRITE ANA {pin:0>3} {analog_adc:0>4}"


class MacroThread(Thread):
    def __init__(
        self,
        should_stop_list: set["MacroThread"],
        target: Callable[..., None] | None,
        *args: Any,
        **kwargs: Any,
    ):
        self.should_stop_list = should_stop_list
        super().__init__(
            target=target,
            args=args,
            kwargs=kwargs,
            daemon=True,
        )
        self._stop_triggered = False

    def trigger_stop(self) -> None:
        self._stop_triggered = True
        self.should_stop_list.add(self)


class Controller:
    def __init__(self, delay: float = 0.01) -> None:
        """
        :param delay: Delay to wait between press and release, defaults to 0.01
        :type delay: float, optional
        """
        self.kc = KController()
        self.mc = MController()
        self.delay = delay
        self.keys_pressed: set[Key | KeyCode] = set()
        self.btns_pressed = set(Button)

        self._macros_threads: dict[str, MacroThread] = {}
        self._macro_threads_that_should_stop: set[MacroThread] = set()
        self._macro_threads_to_be_released: set[MacroThread] = set()

    def on_key_pressed(self, key: Key | KeyCode) -> None:
        self.keys_pressed.add(key)

    def on_key_released(self, key: Key | KeyCode) -> None:
        if key in self.keys_pressed:
            self.keys_pressed.remove(key)

    def on_btn_click(self, x: int, y: int, btn: Button, pressed: bool) -> None:
        if pressed:
            self.btns_pressed.add(btn)
        else:
            if btn in self.btns_pressed:
                self.btns_pressed.remove(btn)

    def is_pressed(self, thing: Key | KeyCode | Button) -> bool:
        if isinstance(thing, Key) or isinstance(thing, KeyCode):
            return thing in self.keys_pressed
        return thing in self.btns_pressed

    def press(
        self,
        key: Key | KeyCode | None = None,
        but: Button | None = None,
    ) -> None:
        if key:
            self.kc.press(key)
        if but:
            self.mc.press(but)

    def release(
        self,
        key: Key | KeyCode | None = None,
        but: Button | None = None,
    ) -> None:
        if key:
            self.kc.release(key)
        if but:
            self.mc.release(but)

    def tap(
        self,
        key: Key | KeyCode | None = None,
        but: Button | None = None,
        delay: float | None = None,
    ) -> None:
        """Press and release a key and/or button with self.delay in between."""
        self.press(key, but)
        time.sleep(self.delay if delay is None else delay)
        self.release(key, but)

    def scroll(self, dx: int, dy: int) -> None:
        """Scroll a certain amount of times."""
        try:
            self.mc.scroll(dx, dy)
        except ValueError:
            pass

    def type(self, text: str) -> None:
        """Type a text."""
        try:
            self.kc.type(text)
        except self.kc.InvalidCharacterException:
            pass

    @contextmanager
    def mod(
        self, *keys: tuple[Key | KeyCode]
    ) -> Generator[None, None, None]:
        """
        Contextmanager to execute a block with some keys pressed. Checks and
        preserves the previous key states of modifiers.
        """
        to_be_released: list[Key] = []
        for key in keys:
            if not self.is_pressed(key):
                self.press(key)
                to_be_released.append(key)

        try:
            yield
        finally:
            for key in reversed(to_be_released):
                self.release(key)

    def ctrl(
        self,
        key: Key | KeyCode | None = None,
        but: Button | None = None,
    ) -> None:
        """Tap a key and/or button together with CTRL."""
        with self.mod(Key.ctrl):
            self.press(key, but)

    def shift(
        self,
        key: Key | KeyCode | None = None,
        but: Button | None = None,
    ) -> None:
        """Tap a key and/or button together with SHIFT."""
        with self.mod(Key.shift):
            self.press(key, but)

    def alt(
        self,
        key: Key | KeyCode | None = None,
        but: Button | None = None,
    ) -> None:
        """Tap a key and/or button together with ALT."""
        with self.mod(Key.alt):
            self.press(key, but)

    def alt_gr(
        self,
        key: Key | KeyCode | None = None,
        but: Button | None = None,
    ) -> None:
        """Tap a key and/or button together with ALT GR."""
        with self.mod(Key.alt_gr):
            self.press(key, but)

    def cmd(
        self,
        key: Key | KeyCode | None = None,
        but: Button | None = None,
    ) -> None:
        """Tap a key and/or button together with CMD."""
        with self.mod(Key.cmd):
            self.press(key, but)

    @staticmethod
    def _parse_shortcut(
        shortcut: str
    ) -> list[tuple[list[Key], KeyCode | None]]:
        """
        Parses Qt KeySequences into pynput keys.

        :param shortcut: A string containing a Qt-Style Key Sequence
        :type shortcut: str
        :return: A list of key combinations. Those are tuple with first a list
        of modifier keys, and second a single KeyCode (or None if the combo
        only contains modifiers)
        :rtype: list[tuple[list[Key], KeyCode | None]]
        """
        cuts: list[tuple[list[Key], KeyCode | None]] = []
        combos = map(str.strip, shortcut.split(","))
        for combo in combos:
            key: str | None
            *mods, key = combo.split("+")
            if key in KEY_LOOKUP:
                mods.append(key)
                key = None
            trans_mods: list[Key] = []
            for mod in mods:
                if (result := KEY_LOOKUP.get(mod)):
                    trans_mods.append(result)
            if key is None:
                key_code = None
            else:
                try:
                    key_code = KeyCode.from_char(key)
                except Exception:
                    pass
            cuts.append((trans_mods, key_code))
        return cuts

    def issue_macro(self, state: bool, macro: MACRO) -> None:
        mode: str | int = macro["mode"]  # type: ignore[assignment]
        name: str = macro["name"]  # type: ignore[assignment]
        actions: list[MACRO_ACTION] = macro["actions"]  # type: ignore[assignment]  # noqa

        if state:
            if name in self._macros_threads:
                if mode != "until_pressed_again":
                    return
                thread = self._macros_threads[name]
                self._macros_threads[name].trigger_stop()
                if thread in self._macro_threads_to_be_released:
                    self._macro_threads_to_be_released.remove(thread)
            else:
                thread = MacroThread(
                    self._macro_threads_that_should_stop,
                    self._exec_macro,
                    m_name=name,
                    m_mode=mode,
                    m_actions=actions,
                )
                self._macros_threads[name] = thread
                if mode == "until_pressed_again":
                    self._macro_threads_to_be_released.add(thread)
                thread.start()
        else:
            if name in self._macros_threads:
                if mode != "until_released":
                    return
                self._macros_threads[name].trigger_stop()

    def _exec_macro(
        self,
        m_name: str,
        m_mode: str,
        m_actions: list[MACRO_ACTION],
    ) -> None:
        def run() -> None:
            for action in m_actions:
                type = action["type"]
                value = action["value"]
                if type in ("press_key", "release_key"):
                    if not isinstance(value, str):
                        return
                    shortcuts = self._parse_shortcut(value)
                    for combo in shortcuts:
                        mods, key_code = combo
                        all_keys: list[Key | KeyCode | None] = [
                            *mods, key_code
                        ]
                        for key in all_keys:
                            if key is None:
                                continue
                            if type == "press_key":
                                self.press(key)
                            else:
                                self.release(key)
                elif type == "delay":
                    if not isinstance(value, int):
                        return
                    time.sleep(value / 1000)
                elif type == "left_mouse_button_down":
                    self.press(but=Button.left)
                elif type == "left_mouse_button_up":
                    self.press(but=Button.left)
                elif type == "middle_mouse_button_down":
                    self.press(but=Button.middle)
                elif type == "middle_mouse_button_up":
                    self.press(but=Button.middle)
                elif type == "right_mouse_button_down":
                    self.press(but=Button.right)
                elif type == "right_mouse_button_up":
                    self.press(but=Button.right)
                elif type == "scroll_up":
                    if not isinstance(value, int):
                        return
                    self.scroll(0, value)
                elif type == "scroll_down":
                    if not isinstance(value, int):
                        return
                    self.scroll(0, -value)
                elif type == "type_text":
                    if not isinstance(value, str):
                        return
                    self.type(value)

        if isinstance(m_mode, int):
            for _ in range(m_mode):
                run()

        else:
            while True:
                run()
                thread = self._macros_threads[m_name]
                if thread in self._macro_threads_that_should_stop:
                    break
                time.sleep(0.01)

        del self._macros_threads[m_name]

    def issue_shortcut(self, state: bool, shortcut: str) -> None:
        shortcuts = self._parse_shortcut(shortcut)
        for combo in shortcuts:
            mods, key_code = combo
            all_keys: list[Key | KeyCode | None] = [
                *mods, key_code
            ]
            for key in all_keys:
                if key is None:
                    continue
                if state:
                    self.press(key)
                else:
                    self.release(key)


def start_controller() -> Controller:
    controller = Controller()
    kl = KListener(
        on_press=controller.on_key_pressed,
        on_release=controller.on_key_released,
    )
    ml = MListener(
        on_click=controller.on_btn_click,
    )
    kl.start()
    ml.start()
    return controller


CONTROLLER = start_controller()
