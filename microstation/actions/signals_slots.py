from pathlib import Path
from typing import Any

import psutil

try:
    from ..enums import Tag
except ImportError:
    from microstation.enums import Tag


INSTANCES: dict[type["SignalOrSlot"], "SignalOrSlot"] = {}


class Param:
    def __init__(
        self, name: str, desc: str, type_: type,
        default: int | float | bool | str | None = None,
        info: dict[str, int | float | bool | str] = {},
    ) -> None:
        self.name = name
        self.desc = desc
        self.type = type_
        self.default = default or self.type()
        self.info = info


class SignalOrSlot:
    NAME = "Unnamed Signal/Slot"
    TAGS: list[Tag] = []
    PARAMS: list[Param] = []
    DEVICES: list[str] = []

    def call(self, signal_slot: str, *args: Any, **kwargs: Any) -> Any | None:
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
        return self.program in (
            p.name() for p in psutil.process_iter(attrs=['name'])
        )


SIGNALS_SLOTS: list[type[SignalOrSlot]] = [
    Nothing,
    NothingManager,
    LogToFile,
    ProgramRunning,
]
