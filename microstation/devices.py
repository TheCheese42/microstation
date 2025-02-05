try:
    from .enums import Tag
    from .model import Device, Pin
except ImportError:
    from enums import Tag  # type: ignore[no-redef]  # noqa: F401
    from model import Device, Pin  # type: ignore[no-redef]  # noqa: F401


class Button(Device):
    NAME = "Button"
    TAGS = [Tag.INPUT, Tag.DIGITAL]
    PINS = [Pin(type="digital", io_type="input")]
    CONFIG = {
        "debounce_time": {
            "type": int, "default": 20, "min": 0, "max": 9999
        }
    }


class LED(Device):
    NAME = "LED"
    TAGS = [Tag.OUTPUT, Tag.DIGITAL, Tag.ANALOG]
    PINS = [Pin(type="both", io_type="output")]


class Potentiometer(Device):
    NAME = "Potentiometer"
    TAGS = [Tag.INPUT, Tag.ANALOG]
    PINS = [Pin(type="analog", io_type="input")]
    CONFIG = {
        "jitter_tolerance": {
            "type": int, "default": 2, "min": 0, "max": 999999
        }
    }


class RGB(Device):
    NAME = "RGB"
    TAGS = [Tag.OUTPUT, Tag.DIGITAL, Tag.ANALOG]
    PINS = [
        Pin(type="both", io_type="output", name="red"),
        Pin(type="both", io_type="output", name="green"),
        Pin(type="both", io_type="output", name="blue"),
    ]


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


__all__ = [
    "Button",
    "LED",
    "Potentiometer",
    "RGB",
    "RotaryEncoder",
]
