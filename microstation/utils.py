import sys

import serial.tools.list_ports_common
from serial.tools.list_ports import comports


def get_port_info(port_str: str) -> str | None:
    for port in comports():
        if port.name == port_str:
            return get_device_info(port)
    return None


def get_device_info(port: serial.tools.list_ports_common.ListPortInfo) -> str:
    if sys.platform.startswith("linux"):
        import pyudev
        context = pyudev.Context()
        device = pyudev.Devices.from_device_file(context, port.device)
        model: str = device.properties.get(
            "ID_MODEL_FROM_DATABASE",
            device.properties.get("ID_MODEL", "Unknown Board"),
        )
        return model
    elif sys.platform.startswith("win"):
        return port.description or "Unknown Board"
    else:
        return "Unknown Board"
