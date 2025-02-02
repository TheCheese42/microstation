"""
Microstation uses semantic versioning.

Major.Minor.Patch

Important: When the Arduino Sketch is modified in a way that breaks backwards
compatibility, always increase Minor.
This will make the GUI ask the User to re-upload the code.
"""

__version__ = (0, 2, 1)
version_string = ".".join(map(str, __version__))
