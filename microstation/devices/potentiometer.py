try:
    from ..enums import Tag
    from ..model import Device, Pin
except ImportError:
    from enums import Tag  # type: ignore[no-redef]  # noqa: F401
    from model import Device, Pin  # type: ignore[no-redef]  # noqa: F401


class Potentiometer(Device):
    NAME = "Potentiometer"
    TAGS = [Tag.INPUT, Tag.ANALOG]
    PINS = [Pin(type="analog", io_type="input")]
    CONFIG = {
        "jitter_tolerance": {
            "type": int, "default": 2, "min": 0, "max": 999999
        }
    }


__all__ = ["Potentiometer"]
