from enum import IntEnum, StrEnum


class Issue(IntEnum):
    NONE = 0
    DUPLICATED_PIN = 1
    COMPONENT_PINS_NOT_MATCHING_DEVICE = 3


class Tag(StrEnum):
    INPUT = "input"
    OUTPUT = "output"
    ANALOG = "analog"
    DIGITAL = "digital"
    CONVERTER = "converter"
    MANAGER = "manager"
