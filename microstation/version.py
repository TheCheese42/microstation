"""
Microstation uses semantic versioning.

Major.Minor.Patch

Important: When the Arduino Sketch is modified in a way that breaks backwards
compatibility, always increase Minor.
This will make the GUI ask the User to re-upload the code.
"""

from .paths import VERSION_PATH

version_string = VERSION_PATH.read_text(encoding="utf-8").strip()
__version__: tuple[int, ...] = tuple(map(int, version_string.split(".")))
