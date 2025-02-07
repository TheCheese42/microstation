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
    from paths import ROOT_PATH

version_path = ROOT_PATH / "version.txt"
version_string = version_path.read_text(encoding="utf-8").strip()
__version__: tuple[int, int, int] = tuple(version_string.split("."))

