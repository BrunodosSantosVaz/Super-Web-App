"""Entry point for WebApps Manager application.

This module provides the main() function that initializes and runs
the GTK application.
"""

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")

from gi.repository import Gdk, Gtk

from .application import WebAppsApplication
from .utils.logger import Logger, get_logger

logger = get_logger(__name__)


def main() -> int:
    """Main entry point for the application.

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    try:
        # Check for debug mode
        if "--debug" in sys.argv:
            Logger.set_debug_mode(True)
            sys.argv.remove("--debug")
            logger.info("Debug mode enabled")

        logger.info("Starting WebApps Manager...")

        # Ensure a graphical session is available before registering the app
        init_result = Gtk.init_check()
        if isinstance(init_result, tuple):
            initialized, error = init_result
        else:
            initialized = bool(init_result)
            error = None

        display = Gdk.Display.get_default() if initialized else None

        if not initialized or display is None:
            logger.error(
                "Não foi possível inicializar o GTK. Execute dentro de uma sessão gráfica (Wayland/X11)."
            )
            if error:
                logger.error("Detalhes: %s", error.message)
            return 1

        # Create and run application
        app = WebAppsApplication()
        exit_code = app.run(sys.argv)

        logger.info(f"Application exited with code: {exit_code}")
        return exit_code

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        return 130

    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
