try:
    from ..model import Device, Pin, Tag
except ImportError:
    from model import Device, Pin, Tag  # type: ignore[no-redef]  # noqa: F401


class LED(Device):
    NAME = "LED"
    TAGS = [Tag.OUTPUT, Tag.DIGITAL, Tag.ANALOG]
    PINS = [Pin(type="both", io_type="output")]


__all__ = ["LED"]
