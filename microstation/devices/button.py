try:
    from ..enums import Tag
    from ..model import Device, Pin
except ImportError:
    from enums import Tag  # type: ignore[no-redef]  # noqa: F401
    from model import Device, Pin  # type: ignore[no-redef]  # noqa: F401


class Button(Device):
    NAME = "Button"
    TAGS = [Tag.INPUT, Tag.DIGITAL]
    PINS = [Pin(type="digital", io_type="input")]


__all__ = ["Button"]
