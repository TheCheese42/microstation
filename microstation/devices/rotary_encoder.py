try:
    from ..model import Device, Pin, Tag
except ImportError:
    from model import Device, Pin, Tag  # type: ignore[no-redef]  # noqa: F401


class RotaryEncoder(Device):
    NAME = "Rotary Encoder"
    TAGS = [Tag.INPUT, Tag.DIGITAL]
    PINS = [
        Pin(type="digital", io_type="input", name="CLK"),
        Pin(type="digital", io_type="input", name="DT"),
    ]


__all__ = ["RotaryEncoder"]
