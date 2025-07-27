import asyncio
from collections.abc import Callable
from contextlib import redirect_stderr
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import psutil
from dbus_fast.errors import DBusError
from desktop_notifier import DesktopNotifier
from desktop_notifier.common import Icon
from pynput.keyboard import Key
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QApplication

from ..enums import Tag
from ..paths import ICONS_PATH
from ..utils import NullStream

if TYPE_CHECKING:
    from ..model import Component, Controller


tr = QApplication.translate


NOTIFIER = DesktopNotifier(
    "Microstation",
    Icon(ICONS_PATH / "aperture.png"),
)


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

    def call_manager(
        self,
        component: "Component",
        write_method: Callable[[str], None],
    ) -> None:
        return


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


class DesktopNotification(SignalOrSlot):
    NAME = "Desktop Notification"
    TAGS = [Tag.INPUT, Tag.DIGITAL]
    PARAMS = [
        Param(
            name="title",
            desc="Title",
            type_=str,
            default="",
            info={
                "tooltip": tr("SignalsSlots", "Notification title")
            },
        ),
        Param(
            name="message",
            desc="Message",
            type_=str,
            default="",
            info={
                "tooltip": tr("SignalsSlots", "Notification content")
            },
        )
    ]

    def __init__(self) -> None:
        self.title = ""
        self.message = ""

    def call(self, signal_slot: str, value: int) -> None:
        async def send_notification() -> None:
            with redirect_stderr(NullStream()):
                try:
                    await NOTIFIER.send(self.title, self.message)
                except DBusError as e:
                    from ..config import log
                    log(f"Received DBusError while sending notification: {e}",
                        "INFO")

        asyncio.get_event_loop().create_task(send_notification())


class ChangeVolume(SignalOrSlot):
    NAME = "Change Volume"
    TAGS = [Tag.INPUT, Tag.DIGITAL]
    PARAMS = [
        Param(
            name="steps",
            desc="Steps",
            type_=int,
            default=0,
            info={
                "min": -100, "max": 100,
                "tooltip": tr("SignalsSlots", "How much the volume should be "
                              "changed. Negative means to lower the volume. "
                              "Zero means that the volume will be increased or"
                              " decreased depending on wether the pin is high "
                              "or low.")
            },
        )
    ]

    def __init__(self) -> None:
        self.steps = 0

    def call(self, signal_slot: str, value: int) -> None:
        if self.steps == 0:
            self.steps = 1 if value else -1
        if self.steps > 0:
            key = Key.media_volume_up
        else:
            key = Key.media_volume_down
        for _ in range(abs(self.steps)):
            get_controller().tap(key)


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


# #################### Managers #####################


class DisplayTime(SignalOrSlot):
    NAME = "Display Time"
    TAGS = [Tag.OUTPUT, Tag.MANAGER]
    DEVICES = ["SSD1306 OLED Display"]

    def __init__(self) -> None:
        self.last_time = ""

    def call_manager(
        self,
        component: "Component",
        write_method: Callable[[str], None],
    ) -> None:
        time_fmt = datetime.now().strftime("%H:%M:%S")
        if self.last_time != time_fmt:
            self.last_time = time_fmt
            write_method(f"DISPLAY_PRINT {time_fmt}")


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
    DesktopNotification,
    ChangeVolume,
    # Slots
    ProgramRunning,
    # Managers
    DisplayTime,
]
