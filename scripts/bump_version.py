#!/usr/bin/env python3

import argparse
from pathlib import Path
import sys

from microstation.version import version_string, __version__, VERSION_PATH


PYPROJECT_PATH = Path() / "pyproject.toml"


def main():
    parser = argparse.ArgumentParser(
        prog="version-bumper",
        description="Bump the version number. Sets the version for all files "
                    "containing a version number, including version.txt, "
                    "pyproject.toml, and the windows installer script.",
    )

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"jsondb-cli {version_string}",
    )
    parser.set_defaults(func=lambda _: parser.print_help())

    parser.add_argument(
        "--major",
        action="store_true",
        required=False,
        default=False,
        dest="major",
        help="Increase the major version.",
    )
    parser.add_argument(
        "--minor",
        action="store_true",
        required=False,
        default=False,
        dest="minor",
        help="Increase the minor version.",
    )
    parser.add_argument(
        "--patch",
        action="store_true",
        required=False,
        default=False,
        dest="patch",
        help="Increase the patch version.",
    )

    args = parser.parse_args(argv)
    to_modify: tuple[bool, bool, bool] = (args.major, args.minor, args.patch)
    if sum(to_modify) > 1:
        print("You mustn't specify more than 1 version option.")
        sys.exit(1)
    new_version: list[int] = list(__version__)
    if to_modify[0]:
        new_version[0] += 1
        new_version[1] = 0
        new_version[2] = 0
    elif to_modify[1]:
        new_version[1] += 1
        new_version[2] = 0
    elif to_modify[2]:
        new_version[2] += 1
    new_tuple: tuple[int, int, int] = tuple(new_version)
    if new_tuple == new_version:
        return
    new_string = ".".join(new_tuple)

    VERSION_PATH.write_text(new_string, encoding="utf-8")


if __name__ == "__main__":
    main()

