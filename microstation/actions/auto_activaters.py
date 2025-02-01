from collections.abc import Callable

import psutil


def program_running(program: str) -> bool:
    return program in (p.name() for p in psutil.process_iter(attrs=['name']))


ACTIVATERS: dict[str, tuple[Callable[..., bool], dict[str, type]]] = {
    "Program Running": (program_running, {"program": str}),
}
