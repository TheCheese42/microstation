try:
    from .gui import launch_gui
except ImportError:
    from gui import launch_gui  # type: ignore[no-redef]


def main() -> None:
    app, win = launch_gui()
    win.show()
    app.exec()


if __name__ == "__main__":
    main()
