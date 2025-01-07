try:
    from ..enums import Tag
    from ..model import Device, Pin
except ImportError:
    from enums import Tag  # type: ignore[no-redef]  # noqa: F401
    from model import Device, Pin  # type: ignore[no-redef]  # noqa: F401


class RotaryEncoder(Device):
    NAME = "Rotary Encoder"
    TAGS = [Tag.INPUT, Tag.DIGITAL]
    PINS = [
        Pin(type="digital", io_type="input", name="CLK"),
        Pin(type="digital", io_type="input", name="DT"),
    ]
    CONFIG = {
        "sensitivity": {
            "type": int, "default": 1, "min": 1, "max": 9999
        }
    }


__all__ = ["RotaryEncoder"]
