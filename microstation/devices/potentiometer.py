try:
    from ..model import Device, Pin, Tag
except ImportError:
    from model import Device, Pin, Tag  # type: ignore[no-redef]  # noqa: F401


class Potentiometer(Device):
    NAME = "Potentiometer"
    TAGS = [Tag.INPUT, Tag.ANALOG]
    PINS = [Pin(type="analog", io_type="input")]


__all__ = ["Potentiometer"]
