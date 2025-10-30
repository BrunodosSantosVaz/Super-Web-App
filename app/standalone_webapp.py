"""Standalone webapp launcher.

This module runs a single webapp in a separate process,
completely independent from the main application.
"""

import sys
import atexit
import os
import signal
from pathlib import Path
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")

from gi.repository import Adw, Gtk, GLib

from .data.database import Database
from .core.webapp_manager import WebAppManager
from .ui.webapp_window import WebAppWindow
from .utils.logger import Logger, get_logger
from .utils.xdg import XDGDirectories, build_app_instance_id
from .webengine.profile_manager import ProfileManager

logger = get_logger(__name__)


class StandaloneWebAppApplication(Adw.Application):
    """Standalone application for a single webapp."""

    def __init__(self, webapp_id: str) -> None:
        """Initialize standalone webapp application.

        Args:
            webapp_id: ID of the webapp to launch
        """
        # Use unique application ID for each webapp to separate in taskbar
        unique_app_id = build_app_instance_id(webapp_id)
        super().__init__(application_id=unique_app_id)

        self.webapp_id = webapp_id
        self.database = None
        self.webapp_manager = None
        self.profile_manager = None
        self.webapp_window = None

        logger.info(f"StandaloneWebAppApplication initialized for {webapp_id} (ID: {unique_app_id})")

    def do_startup(self) -> None:
        """Application startup - initialize components."""
        Adw.Application.do_startup(self)

        logger.info(f"Starting standalone webapp: {self.webapp_id}")

        # Initialize database
        db_path = XDGDirectories.get_database_path()
        self.database = Database(db_path)
        logger.debug(f"Database initialized: {db_path}")

        # Initialize profile manager
        self.profile_manager = ProfileManager()

        # Initialize webapp manager
        self.webapp_manager = WebAppManager(self.database, self.profile_manager)

        logger.debug("Standalone webapp components initialized")

    def do_activate(self) -> None:
        """Application activation - create and show webapp window."""
        logger.info(f"Activating standalone webapp: {self.webapp_id}")

        # Get webapp data
        webapp = self.webapp_manager.get_webapp(self.webapp_id)
        if not webapp:
            logger.error(f"WebApp not found: {self.webapp_id}")
            self.quit()
            return

        settings = self.webapp_manager.get_webapp_settings(self.webapp_id)
        if not settings:
            logger.error(f"Settings not found for webapp: {self.webapp_id}")
            self.quit()
            return

        # Record open
        self.webapp_manager.record_webapp_opened(self.webapp_id)

        # Create webapp window
        self.webapp_window = WebAppWindow(
            application=self,
            webapp=webapp,
            settings=settings,
            webapp_manager=self.webapp_manager,
            profile_manager=self.profile_manager,
            on_window_closed=self._on_window_closed,
        )

        self.webapp_window.present()
        logger.info(f"Standalone webapp window created for {webapp.name}")

    def _on_window_closed(self, webapp_id: str) -> None:
        """Handle webapp window closed.

        Args:
            webapp_id: ID of the webapp that was closed
        """
        logger.info(f"Standalone webapp window closed: {webapp_id}")
        # Quit the application when window is closed
        self.quit()

    def refresh_branding(self) -> None:
        """Reload metadata (name/icon) and refresh active window/tray."""
        if not self.webapp_manager:
            return

        webapp = self.webapp_manager.get_webapp(self.webapp_id)
        if not webapp:
            logger.warning("WebApp %s not found during refresh", self.webapp_id)
            return

        self.webapp = webapp

        if self.webapp_window:
            self.webapp_window.refresh_branding(webapp)

    def do_shutdown(self) -> None:
        """Application shutdown - cleanup."""
        logger.info(f"Shutting down standalone webapp: {self.webapp_id}")

        if self.database:
            self.database.close()
            logger.debug("Database connection closed")

        Adw.Application.do_shutdown(self)
        logger.info("Standalone webapp shutdown complete")


def main_standalone(webapp_id: str, debug: bool = False) -> int:
    """Main entry point for standalone webapp.

    Args:
        webapp_id: ID of the webapp to launch
        debug: Enable debug logging

    Returns:
        Exit code
    """
    try:
        if debug:
            Logger.set_debug_mode(True)
            logger.info("Debug mode enabled for standalone webapp")

        # Create and run standalone app
        app = StandaloneWebAppApplication(webapp_id)

        pid_file: Optional[Path] = None
        try:
            pid_file = XDGDirectories.get_webapp_pid_file(webapp_id)
            pid_file.write_text(str(os.getpid()), encoding="utf-8")
            logger.debug("PID registrado em %s", pid_file)
        except Exception as exc:
            logger.warning("Não foi possível registrar PID do webapp: %s", exc)

        def cleanup_pid() -> None:
            if pid_file and pid_file.exists():
                try:
                    pid_file.unlink()
                except OSError as remove_exc:
                    logger.debug("Falha ao remover arquivo PID: %s", remove_exc)

        atexit.register(cleanup_pid)

        def _handle_exit_signal(signum, _frame) -> None:
            logger.info("Sinal %s recebido; encerrando webapp %s", signum, webapp_id)
            app.quit()

        for _signal in (signal.SIGTERM, signal.SIGINT):
            try:
                signal.signal(_signal, _handle_exit_signal)
            except Exception as exc:
                logger.debug("Não foi possível registrar handler para %s: %s", _signal, exc)

        def _handle_refresh_signal(signum, _frame) -> None:
            logger.info("Sinal %s recebido; atualizando branding do webapp %s", signum, webapp_id)
            GLib.idle_add(app.refresh_branding)

        try:
            signal.signal(signal.SIGUSR1, _handle_refresh_signal)
        except Exception as exc:
            logger.debug("Não foi possível registrar handler de refresh: %s", exc)

        exit_code = app.run([])

        logger.info(f"Standalone webapp exited with code: {exit_code}")
        return exit_code

    except Exception as e:
        logger.critical(f"Unhandled exception in standalone webapp: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m app.standalone_webapp <webapp_id> [--debug]", file=sys.stderr)
        sys.exit(1)

    webapp_id = sys.argv[1]
    debug = "--debug" in sys.argv

    sys.exit(main_standalone(webapp_id, debug))
