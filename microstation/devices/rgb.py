try:
    from ..enums import Tag
    from ..model import Device, Pin
except ImportError:
    from enums import Tag  # type: ignore[no-redef]  # noqa: F401
    from model import Device, Pin  # type: ignore[no-redef]  # noqa: F401


class RGB(Device):
    NAME = "RGB"
    TAGS = [Tag.OUTPUT, Tag.DIGITAL, Tag.ANALOG]
    PINS = [
        Pin(type="both", io_type="output", name="red"),
        Pin(type="both", io_type="output", name="green"),
        Pin(type="both", io_type="output", name="blue"),
    ]


__all__ = ["RGB"]
