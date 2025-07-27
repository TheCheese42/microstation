import time
from typing import Literal

from .config import log
from .enums import Tag
from .gui import tr
from .model import CONFIG_VALUE, Component, Device, Pin


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
        return ["encoder_rotated", "encoder_rotated_left",
                "encoder_rotated_right", "sw_changed",
                "sw_high", "sw_low"]

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


class ButtonRow(Device):
    NAME = "Button Row"
    TAGS = [Tag.INPUT, Tag.ANALOG]
    PINS = [Pin(
        type="analog", io_type="input", properties=["jitter"]
    )]  # XXX properties=["debounce"])]
    CONFIG = {
        # XXX Debounce is only for digital
        # XXX "debounce_time": {
        # XXX     "type": int, "default": 20, "min": 0, "max": 9999,
        # XXX     "translation": tr("Devices", "Debounce Time"),
        # XXX },
        "buttons": {
            "type": int, "default": 3, "min": 2, "max": 20,
            "translation": tr("Devices", "Buttons"),
            "tooltip": tr("Devices", "How many buttons there are in the row."),
        },
        "voltage_range": {
            "type": int, "default": 5, "min": 1, "max": 50,
            "translation": tr("Devices", "Voltage Range"),
            "tooltip": tr("Devices", "Measured voltage values within this "
                          "range are accepted for the corresponding button. "
                          "Voltages reach from 0 to 100, so 5 is a good "
                          "default."),
        },
        "voltages": {
            "type": str, "default": "30:60:100",
            "translation": tr("Devices", "Voltages"),
            "tooltip": tr("Devices", "The voltages used for each button from "
                          "0 to 100, separated using colons.\n\n"
                          "Example: '30:60:100' (First button has a voltage "
                          "of 30 and so on).\n\nIt's very important that the "
                          "voltages from 0 to 100 do not correspond to the "
                          "output of analogRead();, but are remapped to 0-100."
                          ),
        },
        "jitter_tolerance": {
            "type": int, "default": 2, "min": 0, "max": 999999,
            "translation": tr("Devices", "Jitter Tolerance"),
        },
    }
    CUSTOM_SIGNAL_HANDLER = True

    @classmethod
    def available_signals_digital(
        cls, properties: dict[str, CONFIG_VALUE] | None = None,
    ) -> list[str]:
        if properties:
            buttons = properties.get("buttons")
        else:
            buttons = None
        if buttons is None:
            buttons = cls.CONFIG["buttons"]["default"]  # type: ignore[assignment]  # noqa
        if not isinstance(buttons, int):
            log(f"Property 'buttons' should be an integer (is {buttons})",
                "ERROR")
            return []
        signals: list[str] = []
        for i in range(buttons):
            signals.append(f"digital_changed_{i}")
            signals.append(f"digital_high_{i}")
            signals.append(f"digital_low_{i}")
        return signals

    @classmethod
    def available_signals_analog(
        cls, properties: dict[str, CONFIG_VALUE] | None = None,
    ) -> list[str]:
        return []

    @classmethod
    def custom_signal_handler(
        cls,
        component: Component,
        pin: Pin,
        mode: Literal["digital"] | Literal["analog"],
        state: int | float,
    ) -> None:
        buttons = component.properties.get("buttons")
        if buttons is None:
            buttons = cls.CONFIG["buttons"]["default"]  # type: ignore[assignment]  # noqa
        if not isinstance(buttons, int):
            raise TypeError("buttons must be an integer.")
        voltage_range = component.properties.get("voltage_range")
        if voltage_range is None:
            voltage_range = cls.CONFIG["voltage_range"]["default"]  # type: ignore[assignment]  # noqa
        if not isinstance(voltage_range, int):
            raise TypeError("voltage_range must be an integer.")
        voltages = component.properties.get("voltages")
        if voltages is None:
            voltages = cls.CONFIG["voltages"]["default"]  # type: ignore[assignment]  # noqa
        if not isinstance(voltages, str):
            raise TypeError("voltages must be a string.")
        voltages_list = [i for i in voltages.split(":") if i]
        try:
            int_voltages = list(map(int, voltages_list))
        except TypeError:
            log(
                f"Not all voltage values for component {component} are "
                f"integers: {voltages}", "ERROR"
            )
            return
        for i, voltage in enumerate(int_voltages):
            if (
                state >= voltage - voltage_range / 2
                and state <= voltage + voltage_range / 2
            ):
                button = i
                break
        else:
            # All off
            for button in range(buttons):
                if component.device_data_storage[f"last_state_{button}"]:
                    # Turned off
                    component.emit_signal(f"digital_changed_{button}", state)
                    component.emit_signal(f"digital_low_{button}", state)
                    component.device_data_storage[f"last_state_{button}"] = 0
            return
        if component.device_data_storage.get(f"last_state_{button}"):
            pass  # Button still on
        else:
            # Button turned on
            component.emit_signal(f"digital_changed_{button}", state)
            component.emit_signal(f"digital_high_{button}", state)
        for other_button in range(buttons):
            if other_button == button:
                continue
            if component.device_data_storage.get(f"last_state_{other_button}"):
                component.emit_signal(f"digital_changed_{button}", state)
                component.emit_signal(f"digital_low_{button}", state)
            component.device_data_storage[f"last_state_{other_button}"] = 0
        component.device_data_storage[f"last_state_{button}"] = 1


class SSD1306OLEDDisplay(Device):
    NAME = "SSD1306 OLED Display"
    TAGS = [Tag.OUTPUT]


DEVICES = [
    "Button",
    "LED",
    "Potentiometer",
    "RotaryEncoder",
    "ButtonRow",
    "SSD1306OLEDDisplay",
]
