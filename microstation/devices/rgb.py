try:
    from ..model import Device, Pin, Tag
except ImportError:
    from model import Device, Pin, Tag  # type: ignore[no-redef]  # noqa: F401


class RGB(Device):
    NAME = "RGB"
    TAGS = [Tag.OUTPUT, Tag.DIGITAL, Tag.ANALOG]
    PINS = [
        Pin(type="both", io_type="output", name="red"),
        Pin(type="both", io_type="output", name="green"),
        Pin(type="both", io_type="output", name="blue"),
    ]


__all__ = ["RGB"]
