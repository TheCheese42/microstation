try:
    from ..enums import Tag
    from ..model import Device, Pin
except ImportError:
    from enums import Tag  # type: ignore[no-redef]  # noqa: F401
    from model import Device, Pin  # type: ignore[no-redef]  # noqa: F401


class LED(Device):
    NAME = "LED"
    TAGS = [Tag.OUTPUT, Tag.DIGITAL, Tag.ANALOG]
    PINS = [Pin(type="both", io_type="output")]


__all__ = ["LED"]
