import asyncio
from collections import deque
from typing import Self

import serial

try:
    from .config import log
    from .utils import get_port_info
except ImportError:
    from config import log  # type: ignore[no-redef]
    from utils import get_port_info  # type: ignore[no-redef]


class Device:
    """
    Represents a Serial Device. Should be used as context manager.
    """
    def __init__(self, port: str, baudrate: int) -> None:
        self.port = port
        self.baudrate = baudrate
        try:
            self.ser = serial.Serial(port, baudrate, timeout=1)
        except Exception:
            log(f"Failed to create device {self}", "ERROR")

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
        return self._read(size).decode("utf-8")

    def readline(self) -> str:
        return self._readline().decode("utf-8")

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
            log(f"Failed to open device {self}", "ERROR")
        return self

    def __exit__(
        self, _: type, exc_value: Exception, traceback: object
    ) -> None:
        self.close()


class Daemon:
    def __init__(self, port: str, baudrate: int) -> None:
        self.port = port
        self.baudrate = baudrate
        self.device = Device(port, baudrate)
        self.write_queue: deque[str] = deque()
        self.running = False
        self.paused = False
        self.restart_queued = False
        self.stop_queued = False

    def queue_write(self, data: str) -> None:
        if not self.running:
            log("Queued write while daemon wasn't running", "INFO")
            return
        self.write_queue.append(data)

    async def run(self) -> None:
        should_stop = False
        should_restart = False
        while True:
            self.write_queue.clear()
            if should_stop:
                break
            elif should_restart:
                should_restart = False
                self.restart_queued = False
                self.device = Device(self.port, self.baudrate)
            with self.device as device:
                while True:
                    if self.paused:
                        return
                    if self.restart_queued:
                        should_restart = True
                        break
                    if self.stop_queued:
                        should_stop = True
                        break
                    if device.in_waiting():
                        data = device.readline()
                        task = Task(data)
                        await task.run()
                    if self.write_queue:
                        data = self.write_queue.popleft()
                        device.writeline(data)
                    await asyncio.sleep(0.01)
        await asyncio.sleep(0.1)

    def queue_restart(self) -> None:
        self.restart_queued = True

    def queue_stop(self) -> None:
        self.stop_queued = True

    def set_paused(self, paused: bool) -> None:
        """
        Pauses or unpauses the daemon.
        """
        self.paused = paused


class Task:
    def __init__(self, data: str) -> None:
        self.data = data

    async def run(self) -> None:
        print("Task:", self.data)
