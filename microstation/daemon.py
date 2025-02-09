import asyncio
from collections import deque
from collections.abc import Callable
from typing import Any, Self

import serial

from . import config
from .actions import auto_activaters
from .actions.signals_slots import find_signal_slot, get_ss_instance
from .config import get_config_value, log, log_mc
from .model import Profile
from .utils import get_port_info


class SerialDevice:
    """
    Represents a Serial Device. Should be used as context manager.
    """
    def __init__(self, port: str, baudrate: int) -> None:
        self.port = port
        self.baudrate = baudrate
        try:
            self.ser = serial.Serial(port, baudrate, timeout=1)
        except Exception:
            log(f"Failed to create device {self}", "DEBUG")

    @property
    def name(self) -> str | None:
        try:
            return get_port_info(self.ser.port) or "Unknown Board"
        except AttributeError:
            return "Uninitialized Device"

    def __str__(self) -> str:
        return f"{self.name} on {self.port} at {self.baudrate} baud"

    def _write(self, data: bytes) -> None:
        try:
            self.ser.write(data)
        except Exception:
            log(f"Failed to write to device {self}", "ERROR")

    def write(self, data: str) -> None:
        self._write(data.encode("utf-8"))

    def writeline(self, data: str) -> None:
        self._write(f"{data}\n".encode("utf-8"))

    def _read(self, size: int) -> bytes:
        data = b""
        try:
            data = self.ser.read(size)
        except Exception:
            log(f"Failed to read from device {self}", "ERROR")
        return data

    def _readline(self) -> bytes:
        data = b""
        try:
            data = self.ser.readline()
        except Exception:
            log(f"Failed to read from device {self}", "ERROR")
        return data

    def read(self, size: int) -> str:
        try:
            return self._read(size).decode("utf-8")
        except UnicodeDecodeError:
            return ""

    def readline(self) -> str:
        try:
            return self._readline().decode("utf-8")
        except UnicodeDecodeError:
            return ""

    def in_waiting(self) -> int:
        in_waiting = 0
        try:
            in_waiting = self.ser.in_waiting
        except Exception:
            log(f"Failed to get waiting bytes from device {self}", "ERROR")
        return in_waiting

    def is_open(self) -> bool:
        try:
            is_open: bool = self.ser.is_open
        except Exception:
            is_open = False
        return is_open

    def close(self) -> None:
        try:
            self.ser.close()
        except Exception:
            pass

    def __enter__(self) -> Self:
        try:
            self.ser.open()
        except Exception:
            log(f"Failed to open device {self}", "DEBUG")
        return self

    def __exit__(
        self, _: type, exc_value: Exception, traceback: object
    ) -> None:
        self.close()


class Daemon:
    def __init__(self, port: str, baudrate: int) -> None:
        self.port = port
        self.baudrate = baudrate
        self.device = SerialDevice(port, baudrate)
        self.write_queue: deque[str] = deque()
        self.paused = False
        self.restart_queued = False
        self.stop_queued = False
        self.should_discard_incoming_data = False

        self.profile: Profile | None = self.load_auto_activate_profile()
        self.auto_activation_enabled = get_config_value("auto_detect_profiles")
        self.auto_activate_checker_running = False
        self.slot_runner_running = False
        self.profile_changed = False
        self.mc_version: None | str = None

        self.in_history: list[str] = []
        self.out_history: list[str] = []
        self.full_history: list[str] = []

        self.received_task_callbacks: list[Callable[[str], None]] = []
        self.last_slot_returns: dict[str, Any] = {}

    def load_auto_activate_profile(self) -> Profile | None:
        true_profiles: list[Profile] = []
        for profile in config.PROFILES:
            if profile.auto_activate_manager is True:
                true_profiles.append(profile)
            elif profile.auto_activate_manager:
                for name, activater in auto_activaters.ACTIVATERS.items():
                    if name == profile.auto_activate_manager:
                        callab = activater[0]
                        params = profile.auto_activate_params
                        if callab(**params):
                            true_profiles.append(profile)
        try:
            out = sorted(
                true_profiles,
                key=lambda p: p.auto_activate_priority,
                reverse=True,
            )[0]
        except IndexError:
            out = None
        return out

    def set_profile(self, profile: Profile | None) -> None:
        self.profile = profile
        self.profile_changed = True

    def set_auto_activation_enabled(self, enabled: bool) -> None:
        self.auto_activation_enabled = enabled

    def queue_write(self, data: str) -> None:
        if self.paused:
            log(f"Queued write while daemon wasn't running ({data})", "INFO")
            return
        self.write_queue.append(data)

    async def run(self) -> None:
        if not self.auto_activate_checker_running:
            asyncio.get_event_loop().create_task(
                self.check_for_auto_activate_updates_periodically()
            )
            self.auto_activate_checker_running = True
        if not self.slot_runner_running:
            asyncio.get_event_loop().create_task(self.run_slots())
            self.slot_runner_running = True
        should_stop = False
        should_restart = False
        while True:
            self.write_queue.clear()
            if should_stop:
                log("Stopping Daemon")
                break
            elif should_restart:
                log("Restarting Daemon")
                should_restart = False
                self.restart_queued = False
                self.device = SerialDevice(self.port, self.baudrate)
            with self.device as device:
                if not device.is_open():
                    await asyncio.sleep(1)
                    should_restart = True
                    continue
                while True:
                    await asyncio.sleep(0.01)
                    if self.paused:
                        continue
                    if self.stop_queued:
                        should_stop = True
                        break
                    if self.restart_queued:
                        should_restart = True
                        break
                    if self.should_discard_incoming_data:
                        self.should_discard_incoming_data = False
                        while device.in_waiting():
                            device.readline()
                    if self.profile_changed:
                        self.profile_changed = False
                        asyncio.get_event_loop().create_task(Task(
                            "PINS_REQUESTED", self.queue_write, self,
                            self.profile
                        ).run())
                    if device.in_waiting():
                        data = device.readline().strip()
                        self.in_history.append(data)
                        self.full_history.append(f"[IN] {data}")
                        for cb in self.received_task_callbacks:
                            cb(data)
                        task = Task(data, self.queue_write, self, self.profile)
                        asyncio.get_event_loop().create_task(task.run())
                    if self.write_queue:
                        data = self.write_queue.popleft()
                        self.out_history.append(data)
                        self.full_history.append(f"[OUT] {data}")
                        device.writeline(data)
        await asyncio.sleep(0.1)

    def queue_restart(self) -> None:
        self.restart_queued = True

    def queue_stop(self) -> None:
        self.stop_queued = True

    def set_paused(self, paused: bool) -> None:
        """
        Pauses or unpauses the daemon.
        While paused, serial communication will be lost.
        """
        if self.paused and not paused:
            self.write_queue.clear()
            self.should_discard_incoming_data = True
        self.paused = paused

    async def check_for_auto_activate_updates_periodically(self) -> None:
        while True:
            await asyncio.sleep(0.5)
            if self.auto_activation_enabled:
                self.profile = self.load_auto_activate_profile()

    async def run_slots(self) -> None:
        while True:
            await asyncio.sleep(0.1)
            if not self.profile:
                continue
            for component in self.profile.components:
                for slot, action in component.slots_actions.items():
                    name = action["name"]
                    if not isinstance(name, str):
                        raise TypeError(
                            f"Action name for slot {slot} must be a string, "
                            f"got {type(name)}"
                        )
                    instance = get_ss_instance(find_signal_slot(name))
                    if isinstance(params := action.get("params"), dict):
                        for attr, value in params.items():
                            setattr(instance, attr, value)
                    last_result = self.last_slot_returns.get(
                        f"{component.id}:{slot}"
                    )
                    result = instance.call(slot)
                    if last_result == result:
                        continue
                    self.last_slot_returns[f"{component.id}:{slot}"] = result
                    component.call_slot(slot, result)


class Task:
    def __init__(
        self,
        data: str,
        write_method: Callable[[str], None],
        daemon: Daemon,
        profile: Profile | None,
    ) -> None:
        self.data = data
        self.write_method = write_method
        self.daemon = daemon
        self.profile = profile

    async def run(self) -> None:
        if not self.data:
            return
        log(f"Received Task {self.data}", "DEBUG")
        try:
            await self.exec_task()
        except Exception as e:
            log(f"Task raised an exception ({self.data}): "
                f"{e.__class__.__name__}: {e}", "ERROR")

    async def exec_task(self) -> None:
        if self.data.startswith("DEBUG "):
            log_mc(self.data.split(" ", 1)[1])
        elif self.data.startswith("VERSION"):
            version = self.data.split(" ", 1)[1]
            self.daemon.mc_version = version
        elif self.data.startswith("PINS_REQUESTED"):
            self.daemon.last_slot_returns.clear()
            self.write_method("")  # Ensure that no half line was left over
            self.write_method("RESET_PINS")
            if not self.profile:
                return
            for component in self.profile.components:
                for pin_name, pin_num in component.pins.items():
                    for device_pin in component.device.PINS:
                        if device_pin.name == pin_name:
                            io_type = (
                                "INP" if device_pin.io_type == "input"
                                else "OUT"
                            )
                            type_ = (
                                "DIG" if device_pin.type == "digital"
                                else "ANA"
                            )
                            self.write_method(
                                f"PINMODE {type_} {io_type} {pin_num:0>3}"
                            )
                            if (
                                "debounce_time" in component.device.CONFIG
                                and "debounce" in device_pin.properties
                            ):
                                if not (dt := component.properties.get(
                                    "debounce_time"
                                )):
                                    dt = component.device.CONFIG[
                                        "debounce_time"
                                    ]["default"]  # type: ignore[assignment]
                                self.write_method(
                                    f"DIGITAL_DEBOUNCE {pin_num:0>3} "
                                    f"{dt:0>4}"
                                )
                            if (
                                "jitter_tolerance" in component.device.CONFIG
                                and "jitter" in device_pin.properties
                            ):
                                if not (jt := component.properties.get(
                                    "jitter_tolerance"
                                )):
                                    jt = component.device.CONFIG[
                                        "jitter_tolerance"
                                    ]["default"]  # type: ignore[assignment]
                                self.write_method(
                                    f"ANALOG_TOLERANCE {pin_num:0>3} "
                                    f"{jt:0>6}"
                                )
        elif self.data.startswith("EVENT"):
            if not self.profile:
                return
            _, type_, pin_string, state_string = self.data.split()
            pin = int(pin_string)
            state = int(state_string)
            for component in self.profile.components:
                if pin in component.pins.values():
                    if type_ == "DIGITAL":
                        component.emit_signal("digital_changed", state)
                        component.emit_signal("digital_high", state)
                    elif type_ == "ANALOG":
                        component.emit_signal("analog_changed", state)
