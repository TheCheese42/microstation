import time
from typing import Literal

from .enums import Tag
from .gui import tr
from .model import CONFIG_VALUE, Component, Device, Pin
from .config import log


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
            "tooltip": tr("Devices", "How often the Rotary Encoder must be "
                          "rotated within one second in order to count the "
                          "rotations as one. If you don't know what this "
                          "means, refer to our Wiki or leave it at 1.")
        },
        "debounce_time": {
            "type": int, "default": 20, "min": 0, "max": 9999,
            "translation": tr("Devices", "Debounce Time (SW)"),
        },
        "encoder_debounce_time": {
            "type": int, "default": 20, "min": 0, "max": 9999,
            "translation": tr("Devices", "Encoder Debounce Time"),
        },
    }
    CUSTOM_SIGNAL_HANDLER = True

    @classmethod
    def available_signals_digital(
        cls, properties: dict[str, CONFIG_VALUE] | None = None,
    ) -> list[str]:
        if Tag.INPUT in cls.TAGS and Tag.DIGITAL in cls.TAGS:
            return ["encoder_rotated", "encoder_rotated_left",
                    "encoder_rotated_right", "sw_changed",
                    "sw_high", "sw_low"]
        return []

    @classmethod
    def custom_signal_handler(
        cls,
        component: Component,
        pin: Pin,
        mode: Literal["digital"] | Literal["analog"],
        state: int | float,
    ) -> None:
        if pin.name == "SW":
            component.emit_signal("sw_changed", state)
            if state:
                component.emit_signal("sw_high", state)
            else:
                component.emit_signal("sw_low", state)
        elif pin.name == "CLK":
            if state != component.device_data_storage.get("last_clk"):
                component.device_data_storage["last_clk"] = state
                if (dt := component.device_data_storage.get(
                    "last_dt"
                )) is not None:
                    debounce_time = component.properties.get(
                        "encoder_debounce_time", cls.CONFIG[
                            "encoder_debounce_time"]["default"]
                    )
                    if not isinstance(debounce_time, int):
                        log("Rotary encoder debounce_time is not an integer: "
                            f"{debounce_time}")
                        return
                    if component.device_data_storage.get(
                        "last_time_rotated", 0
                    ) + debounce_time / 1000 > time.time():
                        return
                    if state and not dt:
                        component.device_data_storage[
                            "last_time_rotated"
                        ] = time.time()
                        if component.device_data_storage.get(
                            "sens_start_time", 0
                        ) + 1 < time.time():
                            component.device_data_storage[
                                "sens_start_time"] = time.time()
                            component.device_data_storage[
                                "amount_sens_left"] = 0
                        if "amount_sens_left" in component.device_data_storage:
                            component.device_data_storage[
                                "amount_sens_left"] += 1
                        else:
                            component.device_data_storage[
                                "amount_sens_left"] = 1
                        if component.device_data_storage[
                            "amount_sens_left"
                        ] >= component.properties.get(
                            "sensitivity", cls.CONFIG["sensitivity"]["default"]
                        ):
                            component.device_data_storage[
                                "amount_sens_left"] = 0
                            component.emit_signal("encoder_rotated", 0)
                            component.emit_signal("encoder_rotated_left", 0)
                    elif state and dt:
                        component.device_data_storage[
                            "last_time_rotated"
                        ] = time.time()
                        if component.device_data_storage.get(
                            "sens_start_time", 0
                        ) + 1 < time.time():
                            component.device_data_storage[
                                "sens_start_time"] = time.time()
                            component.device_data_storage[
                                "amount_sens_right"] = 0
                        if "amount_sens_right" in component.device_data_storage:  # noqa: E501
                            component.device_data_storage[
                                "amount_sens_right"] += 1
                        else:
                            component.device_data_storage[
                                "amount_sens_right"] = 1
                        if component.device_data_storage[
                            "amount_sens_right"
                        ] >= component.properties.get(
                            "sensitivity", cls.CONFIG["sensitivity"]["default"]
                        ):
                            component.device_data_storage[
                                "amount_sens_right"] = 0
                            component.emit_signal("encoder_rotated", 1)
                            component.emit_signal("encoder_rotated_right", 1)
        elif pin.name == "DT":
            if state != component.device_data_storage.get("last_dt"):
                component.device_data_storage["last_dt"] = state


__all__ = [
    "Button",
    "LED",
    "Potentiometer",
    "RotaryEncoder",
]
