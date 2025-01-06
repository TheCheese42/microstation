try:
    from ..model import Tag
except ImportError:
    from microstation.model import Tag


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


def find_signal_slot(name: str) -> type[SignalOrSlot]:
    for thing in dir():
        ref: type[SignalOrSlot] = globals()[thing]
        if issubclass(ref, SignalOrSlot) and ref.NAME == name:
            return ref
    raise ValueError(f"Signal or Slot {name} was not found.")


def query_signals_slots(tags: list[Tag]) -> list[type[SignalOrSlot]]:
    signals_slots: list[type[SignalOrSlot]] = []
    for thing in dir():
        ref: type[SignalOrSlot] = globals()[thing]
        if issubclass(ref, SignalOrSlot):
            for tag in tags:
                if tag not in ref.TAGS:
                    break
            else:
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
