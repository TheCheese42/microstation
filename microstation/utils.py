import json
from collections.abc import Generator
from platform import system
from subprocess import getstatusoutput
from urllib.request import urlretrieve
from zipfile import ZipFile

import serial.tools.list_ports_common
from paths import LIB_DIR
from serial.tools.list_ports import comports


def get_port_info(port_str: str) -> str | None:
    for port in comports():
        if port.name in port_str:
            return get_device_info(port)
    return None


def get_device_info(port: serial.tools.list_ports_common.ListPortInfo) -> str:
    if system() == "Linux":
        import pyudev
        context = pyudev.Context()
        device = pyudev.Devices.from_device_file(context, port.device)
        model: str = device.properties.get(
            "ID_MODEL_FROM_DATABASE",
            device.properties.get("ID_MODEL", "Unknown Board"),
        )
        return model
    elif system() == "Windows":
        return port.description or "Unknown Board"
    else:
        return "Unknown Board"


def arduino_cli_path() -> str | None:
    for path in ["arduino-cli", str(LIB_DIR / "arduino-cli" / "arduino-cli")]:
        status, _ = getstatusoutput(path)
        if status == 0:
            return path
    return None


def is_arduino_cli_available() -> bool:
    return bool(arduino_cli_path())


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
    :raises LookupError: arduino-cli is not installed
    :raises RuntimeError: arduino-cli returned non-zero exit code
    :raises RuntimeError: arduino-cli returned an unexpected JSON structure
    :raises RuntimeError: The specified port was not found
    :return: The FQBN of the board
    :rtype: str
    """
    if not is_arduino_cli_available():
        raise LookupError("arduino-cli is not installed")
    status, output = getstatusoutput("arduino-cli board list --json")
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


def upload_code(port: str, path: str) -> None:
    if not is_arduino_cli_available():
        raise LookupError("arduino-cli is not installed")
    fqbn = lookup_fqbn(port)
    status, output = getstatusoutput(
        f"arduino-cli compile --fqbn {fqbn} {path}"
    )
    if status:
        raise RuntimeError(
            f"Error compiling sketch: {output} (status code {status})"
        )
    status, output = getstatusoutput(
        f"arduino-cli upload --port {port} --fqbn {fqbn} {path}"
    )
    if status:
        raise RuntimeError(
            f"Error uploading sketch: {output} (status code {status})"
        )


def update_core_index() -> None:
    status, output = getstatusoutput("arduino-cli core update-index")
    if status:
        raise RuntimeError(
            f"Error updating core index: {output} (status code {status})"
        )


def install_core(core: str) -> None:
    update_core_index()
    status, output = getstatusoutput(f"arduino-cli core install {core}")
    if status:
        raise RuntimeError(
            f"Error installing core: {output} (status code {status})"
        )


def available_boards() -> Generator[tuple[str, str], None, None]:
    """
    Get a list of available boards and their cores.

    :raises RuntimeError: arduino-cli returned a non-zero exit code.
    :yield: A pair of a board name and its core.
    :rtype: Generator[tuple[str, str], None, None]
    """
    update_core_index()
    status, output = getstatusoutput("arduino-cli board listall --json")
    if status:
        raise RuntimeError(
            f"Error fetching boards: {output} (status code {status})"
        )
    for board in json.loads(output)["boards"]:
        name: str = board["name"]
        fqbn: str = board["fqbn"]
        core = ":".join(fqbn.split(":")[:2])
        yield name, core


def update_lib_index() -> None:
    status, output = getstatusoutput("arduino-cli lib update-index")
    if status:
        raise RuntimeError(
            f"Error updating lib index: {output} (status code {status})"
        )


def install_library(name: str) -> None:
    update_lib_index()
    status, output = getstatusoutput(f"arduino-cli lib install {name}")
    if status:
        raise RuntimeError(
            f"Error installing library: {output} (status code {status})"
        )


def upgrade_libraries() -> None:
    update_lib_index()
    status, output = getstatusoutput("arduino-cli lib upgrade")
    if status:
        raise RuntimeError(
            f"Error upgrading libraries: {output} (status code {status})"
        )
