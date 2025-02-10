#!/usr/bin/env python3

import argparse
import re
import sys
from pathlib import Path

sys.path.append(str(Path("microstation")))

from paths import VERSION_PATH  # noqa  # type: ignore
from version import __version__  # noqa  # type: ignore
from version import version_string  # noqa  # type: ignore

PYPROJECT_PATH = Path() / "pyproject.toml"
PRODUCT_WXS_PATH = Path() / "Product.wxs"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="version-bumper",
        description="Bump the version number. Sets the version for all files "
                    "containing a version number, including version.txt, "
                    "pyproject.toml and the Windows installer script.",
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

    args = parser.parse_args()
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
    new_tuple: tuple[int, ...] = tuple(new_version)
    if new_tuple == __version__:
        parser.print_help()
        sys.exit(0)
    new_string = ".".join(map(str, new_tuple))

    VERSION_PATH.write_text(new_string, encoding="utf-8")

    pyproject_text = PYPROJECT_PATH.read_text(encoding="utf-8")
    if match := re.search(r"version = \"([\d\.]*)\"", pyproject_text):
        start = match.start(1)
        pyproject_list = list(pyproject_text)
        del pyproject_list[start:match.end(1)]
        for i, char in enumerate(new_string):
            pyproject_list.insert(start + i, char)
        PYPROJECT_PATH.write_text("".join(pyproject_list), encoding="utf-8")
    else:
        print("pyproject.toml doesn't contain a version string.")

    product_wxs_text = PRODUCT_WXS_PATH.read_text(encoding="utf-8")
    if match := re.search(r"Version=\"([\d\.]*)\"", product_wxs_text):
        start = match.start(1)
        product_wxs_list = list(product_wxs_text)
        del product_wxs_list[start:match.end(1)]
        for i, char in enumerate(new_string):
            product_wxs_list.insert(start + i, char)
        PRODUCT_WXS_PATH.write_text(
            "".join(product_wxs_list), encoding="utf-8"
        )
    else:
        print("Product.wxs doesn't contain a version string.")

    print(f"Set Version to {new_string}")


if __name__ == "__main__":
    main()
