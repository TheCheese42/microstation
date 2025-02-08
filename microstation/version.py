"""
Microstation uses semantic versioning.

Major.Minor.Patch

Important: When the Arduino Sketch is modified in a way that breaks backwards
compatibility, always increase Minor.
This will make the GUI ask the User to re-upload the code.
"""

try:
    from .paths import ROOT_PATH
except ImportError:
    from paths import ROOT_PATH  # type: ignore[no-redef]

VERSION_PATH = ROOT_PATH / "version.txt"
version_string = VERSION_PATH.read_text(encoding="utf-8").strip()
__version__: tuple[int, ...] = tuple(map(int, version_string.split(".")))
