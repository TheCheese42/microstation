import asyncio
from collections import deque
from typing import Self

import serial
from serial.tools.list_ports import comports

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
        self.ser = serial.Serial(port, baudrate, timeout=1)

    @property
    def name(self) -> str | None:
        return get_port_info(self.ser.port)

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
        is_open: bool = self.ser.is_open
        return is_open

    def close(self) -> None:
        self.ser.close()

    def __enter__(self) -> Self:
        self.ser.open()
        return self

    def __exit__(
        self, exc_type: type, exc_value: Exception, traceback: object
    ) -> None:
        self.close()


class Daemon:
    def __init__(self, port: str, baudrate: int) -> None:
        self.device = Device(port, baudrate)
        self.write_queue: deque[str] = deque()
        self.running = False

    def queue_write(self, data: str) -> None:
        if not self.running:
            log("Queued write while daemon wasn't running", "INFO")
            return
        self.write_queue.append(data)

    async def run(self) -> None:
        print("run")
        with self.device as device:
            while device.is_open():
                if device.in_waiting():
                    data = device.readline()
                    task = Task(data)
                    await task.run()
                if self.write_queue:
                    data = self.write_queue.popleft()
                    device.writeline(data)

    def restart(self) -> None:
        """
        Completely restarts the daemon. Can also be used to start the daemon.
        """
        self.stop()
        self.device = Device(self.device.port, self.device.baudrate)
        asyncio.tasks.create_task(self.run())
        self.running = True

    def stop(self) -> None:
        """
        Stops the daemon.
        """
        self.device.close()
        self.write_queue.clear()
        for task in asyncio.tasks.all_tasks():
            task.cancel()
        self.running = False


class Task:
    def __init__(self, data: str) -> None:
        self.data = data

    async def run(self) -> None:
        print("Task:", self.data)
