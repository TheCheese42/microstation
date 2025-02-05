try:
    # To ensure they are bundled by nuitka
    from .devices import *  # noqa
except ImportError:
    from devices import *  # noqa
