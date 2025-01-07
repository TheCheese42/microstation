from typing import Any

try:
    from ..enums import Tag
except ImportError:
    from microstation.enums import Tag


INSTANCES: dict[type["SignalOrSlot"], "SignalOrSlot"] = {}


class Param:
    def __init__(
        self, name: str, desc: str, type_: type,
        info: dict[str, int | float | bool | str] = {},
    ) -> None:
        self.name = name
        self.desc = desc
        self.type = type_
        self.info = info


class SignalOrSlot:
    NAME = "Unnamed Signal/Slot"
    TAGS: list[Tag] = []
    PARAMS: list[Param] = []
    DEVICES: list[str] = []

    def call(self, *args: Any, **kwargs: Any) -> Any | None:
        return None


def get_ss_instance(cls: type[SignalOrSlot]) -> SignalOrSlot:
    if cls in INSTANCES:
        return INSTANCES[cls]
    instance = cls()
    INSTANCES[cls] = instance
    return instance


def find_signal_slot(name: str) -> type[SignalOrSlot]:
    for thing in dir():
        try:
            ref: type[SignalOrSlot] = globals()[thing]
        except KeyError:
            continue
        if issubclass(ref, SignalOrSlot) and ref.NAME == name:
            return ref
    raise ValueError(f"Signal or Slot {name} was not found.")


def query_signals_slots(
    tags: list[Tag], include_manager: bool = True,
) -> list[type[SignalOrSlot]]:
    signals_slots: list[type[SignalOrSlot]] = []
    for thing in dir():
        try:
            ref: type[SignalOrSlot] = globals()[thing]
        except KeyError:
            continue
        if issubclass(ref, SignalOrSlot):
            for tag in tags:
                if tag not in ref.TAGS:
                    break
            else:
                if not (include_manager is False and Tag.MANAGER in ref.TAGS):
                    signals_slots.append(ref)
    return signals_slots


def query_by_device(device: str) -> list[type[SignalOrSlot]]:
    signals_slots: list[type[SignalOrSlot]] = []
    for thing in dir():
        try:
            ref: type[SignalOrSlot] = globals()[thing]
        except KeyError:
            continue
        if issubclass(ref, SignalOrSlot):
            if device in ref.DEVICES:
                signals_slots.append(ref)
    return signals_slots


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
