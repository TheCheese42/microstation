import asyncio
import sys
import time
import traceback
from threading import Thread

import pystray
from PIL import Image

try:
    from . import config
    from .daemon import Daemon
    from .gui import Microstation, launch_gui
    from .model import CONTROLLER, start_controller_listeners
    from .paths import ICONS_PATH
except ImportError:
    import config  # type: ignore[no-redef]
    from daemon import Daemon  # type: ignore[no-redef]
    from gui import Microstation  # type: ignore[no-redef]
    from gui import launch_gui  # type: ignore[no-redef]
    from model import CONTROLLER  # type: ignore[no-redef]
    from model import start_controller_listeners  # type: ignore[no-redef]
    from paths import ICONS_PATH  # type: ignore[no-redef]


def main() -> None:
    config.init_config()
    config.log_basic()
    start_controller_listeners(CONTROLLER)
    daemon = Daemon(
        config.get_config_value("default_port"),
        config.get_config_value("baudrate"),
    )
    config.PROFILES = config.load_profiles(daemon.queue_write)
    config.MACROS = config.load_macros()
    daemon_thread = Thread(
        target=start_daemon,
        args=(daemon,),
        name="Microstation Daemon",
        daemon=True,
    )
    daemon_thread.start()

    def show_gui(win: Microstation, _) -> None:  # type: ignore[no-untyped-def]
        config.log("Received SHOW signal from tray icon", "DEBUG")
        win.show()
        win.showNormal()

    def quit_app(  # type: ignore[no-untyped-def]
        win: Microstation, icon
    ) -> None:
        config.log("Received QUIT signal from tray icon", "INFO")
        win.request_quit()

    tray_icon = Image.open(ICONS_PATH / "aperture.png")
    icon = pystray.Icon(
        "Microstation", tray_icon, "Microstation",
        menu=pystray.Menu(
            pystray.MenuItem(
                "Show Graphical Interface",
                lambda icon: show_gui(win, icon),
                default=True,
            ),
            pystray.MenuItem(
                "Restart Daemon", lambda _: daemon.queue_restart()
            ),
            pystray.MenuItem("Quit", lambda icon: quit_app(win, icon)),
        )
    )

    def quit_app_full() -> None:
        app.quit()
        icon.stop()
        daemon.queue_stop()
        time.sleep(0.2)
        config.log("Exiting", "INFO")
        sys.exit(0)

    app, win = launch_gui(daemon, quit_app_full)
    if not config.get_config_value("hide_to_tray_startup"):
        win.show()

    icon.run_detached()
    config.log("Started system tray icon", "INFO")

    try:
        code = app.exec()
    except (KeyboardInterrupt, EOFError) as e:
        config.log(f"Received {e.__class__.__name__}, exiting cleanly", "INFO")
    except Exception as e:
        config.log(str(e), "CRITICAL")
        traceback.print_exc(file=config.LogStream("TRACE"))

    daemon.queue_stop()
    time.sleep(0.1)
    config.log("Exiting", "INFO")
    icon.stop()
    sys.exit(code)


def start_daemon(daemon: Daemon) -> None:
    config.log("Starting daemon", "INFO")
    asyncio.new_event_loop().run_until_complete(daemon.run())


if __name__ == "__main__":
    main()
