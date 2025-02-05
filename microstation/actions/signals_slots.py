from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import psutil
from PyQt6.QtGui import QKeySequence

try:
    from ..enums import Tag
except ImportError:
    from enums import Tag  # type: ignore[no-redef]

if TYPE_CHECKING:
    from ..model import Controller


INSTANCES: dict[type["SignalOrSlot"], "SignalOrSlot"] = {}


@cache
def get_controller() -> "Controller":
    try:
        from ..model import CONTROLLER
    except ImportError:
        from microstation.model import CONTROLLER
    return CONTROLLER


class Param:
    def __init__(
        self, name: str, desc: str, type_: type | str,
        default: int | float | bool | str | None = None,
        info: dict[str, int | float | bool | str] = {},
    ) -> None:
        self.name = name
        self.desc = desc
        self.type = type_
        self.default = (
            default or self.type() if isinstance(self.type, type) else ""
        )
        self.info = info


class SignalOrSlot:
    NAME = "Unnamed Signal/Slot"
    TAGS: list[Tag] = []
    PARAMS: list[Param] = []
    DEVICES: list[str] = []

    def call(self, signal_slot: str, *args: Any, **kwargs: Any) -> Any:
        return None


def get_ss_instance(cls: type[SignalOrSlot]) -> SignalOrSlot:
    if cls in INSTANCES:
        return INSTANCES[cls]
    instance = cls()
    INSTANCES[cls] = instance
    return instance


def find_signal_slot(name: str) -> type[SignalOrSlot]:
    for cls in SIGNALS_SLOTS:
        if cls.NAME == name:
            return cls
    raise ValueError(f"Signal or Slot {name} was not found.")


def query_signals_slots(
    tags: list[Tag], include_manager: bool = True,
) -> list[type[SignalOrSlot]]:
    signals_slots: list[type[SignalOrSlot]] = []
    for cls in SIGNALS_SLOTS:
        for tag in tags:
            if tag not in cls.TAGS:
                break
        else:
            if not (include_manager is False and Tag.MANAGER in cls.TAGS):
                signals_slots.append(cls)
    return signals_slots


def query_by_device(device: str) -> list[type[SignalOrSlot]]:
    signals_slots: list[type[SignalOrSlot]] = []
    for cls in SIGNALS_SLOTS:
        if device in cls.DEVICES:
            signals_slots.append(cls)
    return signals_slots


class UniStr(str):
    def __eq__(self, _: object) -> bool:
        return True


class Nothing(SignalOrSlot):
    NAME = "None"
    TAGS = [Tag.INPUT, Tag.OUTPUT, Tag.DIGITAL, Tag.ANALOG]


class NothingManager(SignalOrSlot):
    NAME = "No Manager"
    TAGS = [Tag.INPUT, Tag.OUTPUT, Tag.DIGITAL, Tag.ANALOG, Tag.MANAGER]
    DEVICES = [UniStr()]


# #################### SIGNALS #####################


class Shortcut(SignalOrSlot):
    NAME = "Shortcut by Digital State"
    TAGS = [Tag.INPUT, Tag.DIGITAL]
    PARAMS = [
        Param(
            name="shortcut",
            desc="Shortcut",
            type_=QKeySequence,
        )
    ]

    def __init__(self) -> None:
        self.shortcut = ""

    def call(self, signal_slot: str, value: int) -> None:
        if not self.shortcut:
            return
        get_controller().issue_shortcut(bool(value), self.shortcut)


class PressShortcut(Shortcut):
    NAME = "Press Shortcut"

    def __init__(self) -> None:
        self.shortcut = ""

    def call(self, signal_slot: str, value: int) -> None:
        if not self.shortcut:
            return
        get_controller().issue_shortcut(True, self.shortcut)


class ReleaseShortcut(Shortcut):
    NAME = "Release Shortcut"

    def __init__(self) -> None:
        self.shortcut = ""

    def call(self, signal_slot: str, value: int) -> None:
        if not self.shortcut:
            return
        get_controller().issue_shortcut(False, self.shortcut)


class TapShortcut(Shortcut):
    NAME = "Tap Shortcut"

    def __init__(self) -> None:
        self.shortcut = ""

    def call(self, signal_slot: str, value: int) -> None:
        if not self.shortcut:
            return
        get_controller().issue_shortcut(True, self.shortcut)
        get_controller().issue_shortcut(False, self.shortcut)


class Macro(SignalOrSlot):
    NAME = "Macro"
    TAGS = [Tag.INPUT, Tag.DIGITAL]
    PARAMS = [
        Param(
            name="macro",
            desc="Macro",
            type_="macro",
        )
    ]

    def __init__(self) -> None:
        self.macro = ""

    def call(self, signal_slot: str, value: int) -> None:
        if not self.macro:
            return
        try:
            from ..config import MACROS
        except ImportError:
            from microstation.config import MACROS
        for macro in MACROS:
            if macro["name"] == self.macro:
                target_macro = macro
                break
        else:
            return
        if signal_slot == "digital_changed":
            get_controller().issue_macro(bool(value), target_macro)
        else:
            get_controller().issue_macro(True, target_macro)
            # Immediate False because, if the mode is until_released_again and
            # We only have True states, the Macro will run forever. If done
            # like this, it will always run once.
            get_controller().issue_macro(False, target_macro)


class LogToFile(SignalOrSlot):
    NAME = "Log to File"
    TAGS = [Tag.INPUT, Tag.DIGITAL, Tag.ANALOG]
    PARAMS = [
        Param(
            name="path",
            desc="File Path",
            type_=str,
        )
    ]

    def __init__(self) -> None:
        self.path = ""

    def call(self, signal_slot: str, value: int | float) -> None:
        if not self.path:
            print(value)
        else:
            if (p := Path(self.path)).exists():
                mode = "a"
            else:
                mode = "w"
            with open(p, mode=mode, encoding="utf-8") as fp:
                fp.write(str(value) + "\n")


# ##################### SLOTS ######################


class ProgramRunning(SignalOrSlot):
    NAME = "Program Running"
    TAGS = [Tag.OUTPUT, Tag.DIGITAL]
    PARAMS = [
        Param(
            name="program",
            desc="Program",
            type_=str,
        )
    ]

    def __init__(self) -> None:
        self.program = ""

    def call(self, signal_slot: str) -> bool:
        if not self.program:
            return False
        try:
            is_running = self.program in (
                p.name() for p in psutil.process_iter(attrs=['name'])
            )
        except Exception:
            is_running = False
        return is_running


SIGNALS_SLOTS: list[type[SignalOrSlot]] = [
    Nothing,
    NothingManager,
    # Signals
    Shortcut,
    TapShortcut,
    PressShortcut,
    ReleaseShortcut,
    Macro,
    LogToFile,
    # Slots
    ProgramRunning,
]
