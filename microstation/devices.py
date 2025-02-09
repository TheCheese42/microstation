from .enums import Tag
from .gui import tr
from .model import CONFIG_VALUE, Device, Pin


class Button(Device):
    NAME = "Button"
    TAGS = [Tag.INPUT, Tag.DIGITAL]
    PINS = [Pin(type="digital", io_type="input", properties=["debounce"])]
    CONFIG = {
        "debounce_time": {
            "type": int, "default": 20, "min": 0, "max": 9999,
            "translation": tr("Devices", "Debounce Time"),
        }
    }


class LED(Device):
    NAME = "LED"
    TAGS = [Tag.OUTPUT, Tag.DIGITAL, Tag.ANALOG]
    PINS = [Pin(type="both", io_type="output")]


class Potentiometer(Device):
    NAME = "Potentiometer"
    TAGS = [Tag.INPUT, Tag.ANALOG]
    PINS = [Pin(type="analog", io_type="input", properties=["jitter"])]
    CONFIG = {
        "jitter_tolerance": {
            "type": int, "default": 2, "min": 0, "max": 999999,
            "translation": tr("Devices", "Jitter Tolerance"),
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
        Pin(type="digital", io_type="input", name="SW",
            properties=["debounce"]),
    ]
    CONFIG = {
        "sensitivity": {
            "type": int, "default": 1, "min": 1, "max": 9999,
            "translation": tr("Devices", "Sensitivity"),
        },
        "debounce_time": {
            "type": int, "default": 20, "min": 0, "max": 9999,
            "translation": tr("Devices", "Debounce Time"),
        },
        "sw_debounce_time": {
            "type": int, "default": 20, "min": 0, "max": 9999,
            "translation": tr("Devices", "Debounce Time (SW)"),
        },
    }

    @classmethod
    def available_signals_digital(
        cls, properties: dict[str, CONFIG_VALUE] | None = None,
    ) -> list[str]:
        if Tag.INPUT in cls.TAGS and Tag.DIGITAL in cls.TAGS:
            return ["encoder_rotated", "encoder_rotated_left",
                    "encoder_rotated_right"]
        return []


__all__ = [
    "Button",
    "LED",
    "Potentiometer",
    "RGB",
    "RotaryEncoder",
]
