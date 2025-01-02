try:
    from ..model import Device, Pin, Tag
except ImportError:
    from model import Device, Pin, Tag  # type: ignore[no-redef]  # noqa: F401


class Button(Device):
    NAME = "Button"
    TAGS = [Tag.INPUT, Tag.DIGITAL]
    PINS = [Pin(type="digital", io_type="input")]


__all__ = ["Button"]
