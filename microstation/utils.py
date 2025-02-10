import json
from collections.abc import Generator
from platform import system
from subprocess import getstatusoutput
from typing import NamedTuple
from urllib.request import urlretrieve
from zipfile import ZipFile

import serial.tools.list_ports_common
from serial.tools.list_ports import comports

from .paths import LIB_DIR
from . import config


class MissingArduinoCLIError(FileNotFoundError):
    pass


def format_string(text: str, **kwargs: str) -> str:
    """
    Format a string by replacing {keys} with values from keyword arguments.
    The {} are added automatically.

    :param text: The text to format
    :type text: str
    :return: The formatted text
    :rtype: str
    """
    for key, val in kwargs.items():
        text = text.replace(f"{{{key}}}", val)
    return text


def get_port_info(port_str: str) -> str | None:
    for port in comports():
        if port.name in port_str:
            return get_device_info(port)
    return None


def get_device_info(port: serial.tools.list_ports_common.ListPortInfo) -> str:
    default_text = "Unknown Board"
    if system() == "Linux":
        try:
            import pyudev
            context = pyudev.Context()
            device = pyudev.Devices.from_device_file(context, port.device)
        except Exception:
            return default_text
        model: str = device.properties.get(
            "ID_MODEL_FROM_DATABASE",
            device.properties.get("ID_MODEL", default_text),
        )
        return model
    elif system() == "Windows":
        return port.description or default_text
    else:
        return default_text


def arduino_cli_path() -> str | None:
    for path in ["arduino-cli", str(LIB_DIR / "arduino-cli" / "arduino-cli")]:
        status, _ = getstatusoutput(path)
        if status == 0:
            return path
    return None


def is_arduino_cli_available() -> bool:
    return bool(arduino_cli_path())


class ArduinoCLIVersionInformation(NamedTuple):
    name: str
    version: str
    commit: str
    date: str


def lookup_arduino_cli_information() -> ArduinoCLIVersionInformation:
    """
    Lookup the version information of arduino-cli.

    :raises MissingArduinoCLIError: arduino-cli is not installed
    :raises RuntimeError: arduino-cli returned non-zero exit code
    :raises RuntimeError: arduino-cli returned an unexpected JSON structure
    :return: A named tuple containing all given information
    :rtype: str
    """
    if not is_arduino_cli_available():
        raise MissingArduinoCLIError("arduino-cli is not installed")
    status, output = getstatusoutput(f"{arduino_cli_path()} version --json")
    if status:
        raise RuntimeError(f"{output} (status code {status})")
    json_output: dict[str, str] = json.loads(output)
    try:
        name = json_output["Application"]
        version = json_output["VersionString"]
        commit = json_output["Commit"]
        date = json_output["Date"]
        return ArduinoCLIVersionInformation(name, version, commit, date)
    except Exception:
        raise RuntimeError(
            "Unexpected JSON structure. Outdated arduino-cli?"
        )


def install_arduino_cli() -> None:
    """
    Attempt to install arduino-cli into LIB_DIR/arduino-cli/.

    :raises RuntimeError: An error occurred while installing.
    """
    (LIB_DIR / "arduino-cli").mkdir(parents=True, exist_ok=True)
    system_ = system()
    error: str | None = None
    if system_ == "Windows":
        try:
            urlretrieve(
                "https://downloads.arduino.cc/arduino-cli/"
                "arduino-cli_latest_Windows_64bit.zip",
                LIB_DIR / "arduino-cli.zip",
            )
            with ZipFile(LIB_DIR / "arduino-cli.zip", 'r') as zip_ref:
                zip_ref.extractall(LIB_DIR / "arduino-cli")
        except Exception as e:
            error = str(e)
        (LIB_DIR / "arduino-cli.zip").unlink(True)
    else:
        status, output = getstatusoutput(
            "curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/"
            f"master/install.sh | BINDIR={LIB_DIR / "arduino-cli"} sh"
        )
        if status:
            error = f"{output} (status code {status})"
    if error:
        raise RuntimeError(error)


def lookup_fqbn(port: str) -> str:
    """
    Lookup a board's FQBN using arduino-cli.

    :param port: The port the board is at
    :type port: str
    :raises MissingArduinoCLIError: arduino-cli is not installed
    :raises RuntimeError: arduino-cli returned non-zero exit code
    :raises RuntimeError: arduino-cli returned an unexpected JSON structure
    :raises RuntimeError: The specified port was not found
    :return: The FQBN of the board
    :rtype: str
    """
    if not is_arduino_cli_available():
        raise MissingArduinoCLIError("arduino-cli is not installed")
    status, output = getstatusoutput(f"{arduino_cli_path()} board list --json")
    if status:
        raise RuntimeError(f"{output} (status code {status})")
    json_output: dict[str, list[
        dict[str, dict[str, str] | list[dict[str, str]]]
    ]] = json.loads(output)
    for detected_port in json_output["detected_ports"]:
        try:
            port_ = detected_port["port"]["address"]  # type: ignore  # noqa
            if port == port_:
                return detected_port["matching_boards"][0]["fqbn"]  # type: ignore  # noqa
        except Exception:
            raise RuntimeError(
                "Unexpected JSON structure. Outdated arduino-cli?"
            )
    raise RuntimeError(f"Couldn't find port {port}")


def core_from_fqbn(fqbn: str) -> str:
    return ":".join(fqbn.split(":")[0:2])


def upload_code(port: str, path: str) -> tuple[str, str]:
    """
    Upload a sketch to a Microcontroller.

    :param port: The port of the Microcontroller
    :type port: str
    :param path: The path to the sketch folder
    :type path: str
    :raises MissingArduinoCLIError: arduino-cli is not installed
    :raises RuntimeError: arduino-cli returned non-zero exit code when
    compiling
    :raises RuntimeError: arduino-cli returned non-zero exit code when
    compiling
    :returns: The arduino-cli compilation and upload output as two strings
    within a tuple
    :rtype: tuple[str, str]
    """
    if not is_arduino_cli_available():
        raise MissingArduinoCLIError("arduino-cli is not installed")
    fqbn = lookup_fqbn(port)
    status, c_output = getstatusoutput(
        f"{arduino_cli_path()} compile --fqbn {fqbn} {path} --no-color "
        "--warnings all"
    )
    if status:
        raise RuntimeError(
            f"Error compiling sketch: {c_output} (status code {status})"
        )
    status, u_output = getstatusoutput(
        f"{arduino_cli_path()} upload --port {port} --fqbn {fqbn} {path} "
        "--no-color"
    )
    if status:
        raise RuntimeError(
            f"Error uploading sketch: {u_output} (status code {status})"
        )
    return (c_output, u_output)


def update_core_index() -> None:
    """
    Update the arduino-cli core index.

    :raises MissingArduinoCLIError: arduino-cli is not installed
    :raises RuntimeError: arduino-cli returned non-zero exit code
    """
    if not is_arduino_cli_available():
        raise MissingArduinoCLIError("arduino-cli is not installed")
    command = f"{arduino_cli_path()} core update-index"
    if v := config.get_config_value("board_manager_urls"):
        command += f" --additional-urls {",".join(v)}"
    status, output = getstatusoutput(command)
    if status:
        raise RuntimeError(
            f"Error updating core index: {output} (status code {status})"
        )


def install_core(core: str) -> None:
    """
    Install an arduino-cli core.

    :param core: The core to install. Has the format `PACKAGER:ARCH`
    :type core: str
    :raises MissingArduinoCLIError: arduino-cli is not installed
    :raises RuntimeError: arduino-cli returned a non-zero exit code
    """
    if not is_arduino_cli_available():
        raise MissingArduinoCLIError("arduino-cli is not installed")
    update_core_index()
    command = f"{arduino_cli_path()} core install {core}"
    if v := config.get_config_value("board_manager_urls"):
        command += f" --additional-urls {",".join(v)}"
    status, output = getstatusoutput(command)
    if status:
        raise RuntimeError(
            f"Error installing core: {output} (status code {status})"
        )


def remove_core(core: str) -> None:
    """
    Remove an arduino-cli core.

    :param core: The core to remove. Has the format `PACKAGER:ARCH`
    :type core: str
    :raises MissingArduinoCLIError: arduino-cli is not installed
    :raises RuntimeError: arduino-cli returned a non-zero exit code
    """
    if not is_arduino_cli_available():
        raise MissingArduinoCLIError("arduino-cli is not installed")
    update_core_index()
    status, output = getstatusoutput(
        f"{arduino_cli_path()} core uninstall {core}"
    )
    if status:
        raise RuntimeError(
            f"Error uninstalling core: {output} (status code {status})"
        )


def available_cores() -> Generator[tuple[str, bool, str], None, None]:
    """
    Fetch a list of available cores.

    :raises MissingArduinoCLIError: arduino-cli is not installed
    :raises RuntimeError: arduino-cli returned a non-zero exit code.
    :yield: A pair of a core's display name, wether it's installed and its id.
    :rtype: Generator[tuple[str, str], None, None]
    """
    if not is_arduino_cli_available():
        raise MissingArduinoCLIError("arduino-cli is not installed")
    update_core_index()
    status, output = getstatusoutput(
        f"{arduino_cli_path()} core search --json"
    )
    if status:
        raise RuntimeError(
            f"Error fetching cores: {output} (status code {status})"
        )
    for platform in json.loads(output)["platforms"]:
        try:
            id: str = platform["id"]
            latest_version = platform["latest_version"]
            name = platform["releases"][latest_version]["name"]
            try:
                installed = platform["releases"][latest_version]["installed"]
            except KeyError:
                installed = False
        except Exception:
            raise RuntimeError(
                "Unexpected JSON structure. Outdated arduino-cli?"
            )
        yield name, installed, id


def update_lib_index() -> None:
    """
    Update the arduino-cli lib index.

    :raises MissingArduinoCLIError: arduino-cli is not installed
    :raises RuntimeError: arduino-cli returned non-zero exit code
    """
    if not is_arduino_cli_available():
        raise MissingArduinoCLIError("arduino-cli is not installed")
    status, output = getstatusoutput(f"{arduino_cli_path()} lib update-index")
    if status:
        raise RuntimeError(
            f"Error updating lib index: {output} (status code {status})"
        )


def install_library(name: str) -> None:
    """
    Install an arduino-cli library.

    :param name: The name of the library
    :type name: str
    :raises MissingArduinoCLIError: arduino-cli is not installed
    :raises RuntimeError: arduino-cli returned non-zero exit code
    """
    if not is_arduino_cli_available():
        raise MissingArduinoCLIError("arduino-cli is not installed")
    update_lib_index()
    status, output = getstatusoutput(
        f"{arduino_cli_path()} lib install {name}"
    )
    if status:
        raise RuntimeError(
            f"Error installing library: {output} (status code {status})"
        )


def upgrade_libraries() -> None:
    """
    Upgrade all installed arduino-cli libraries.

    :raises MissingArduinoCLIError: arduino-cli is not installed
    :raises RuntimeError: arduino-cli returned non-zero exit code
    """
    if not is_arduino_cli_available():
        raise MissingArduinoCLIError("arduino-cli is not installed")
    update_lib_index()
    status, output = getstatusoutput(f"{arduino_cli_path()} lib upgrade")
    if status:
        raise RuntimeError(
            f"Error upgrading libraries: {output} (status code {status})"
        )


def progress_bar_animation_snappy(
    time: float, time_per_loop: float = 1.4,
) -> tuple[int, bool]:
    """
    Create a hopefully snappy animation for a progress bar to act like a
    loading bar. Returns values from 0 to 1000. Goes infinitely.

    :param time: Time since animation start in seconds
    :type time: float
    :return: The progress bar value and wether the direction should be
    left-to-right (True) or right-to-left (False)
    :rtype: tuple[int, bool]
    """
    def f(x: float) -> float:
        x = x / 1000 * 500 + 500
        result: float = 1.007 ** x - 70
        return result if result >= 0 else 0

    time_withing_loop = time % time_per_loop
    num_loops_past = time // time_per_loop
    max_time_one_side = time_per_loop / 2
    if num_loops_past % 2 == 0:
        if time_withing_loop < time_per_loop / 2:
            return (
                round(f(time_withing_loop * (100 / max_time_one_side) * 10)),
                True
            )
        time_from_half = time_withing_loop - max_time_one_side
        time_withing_loop -= time_from_half * 2
        return (
            round(f(time_withing_loop * (100 / max_time_one_side) * 10)),
            False
        )
    else:
        if time_withing_loop < time_per_loop / 2:
            return (
                round(f(time_withing_loop * (100 / max_time_one_side) * 10)),
                False
            )
        time_from_half = time_withing_loop - max_time_one_side
        time_withing_loop -= time_from_half * 2
        return (
            round(f(time_withing_loop * (100 / max_time_one_side) * 10)),
            True
        )
