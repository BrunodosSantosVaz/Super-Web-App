"""Main application class.

This module provides the main GTK Application class that coordinates
all components and manages the application lifecycle.
"""

import argparse
import sys
from dataclasses import dataclass
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from .core.desktop_integration import DesktopIntegration
from .core.webapp_manager import WebAppManager
from .data.database import Database
from .data.models import AppSettings
from .ui.main_window import MainWindow
from .ui.preferences_dialog import PreferencesDialog
from .utils.logger import get_logger
from .utils.i18n import gettext as _, set_language
from .utils.xdg import APP_ID, XDGDirectories
from .webengine.profile_manager import ProfileManager

logger = get_logger(__name__)


@dataclass
class _CLIOptions:
    """Represent parsed command line options."""

    webapp_id: Optional[str] = None
    new_window: bool = False
    show_preferences: bool = False
    show_main_window: bool = False


class WebAppsApplication(Adw.Application):
    """Main application class.

    Manages application lifecycle, creates windows, and coordinates
    all major components.
    """

    def __init__(self) -> None:
        """Initialize application."""
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )

        # Core components (initialized in do_startup)
        self.database: Optional[Database] = None
        self.profile_manager: Optional[ProfileManager] = None
        self.webapp_manager: Optional[WebAppManager] = None
        self.app_settings: Optional[AppSettings] = None

        # Windows
        self.main_window: Optional[MainWindow] = None
        self._suppress_main_window = False
        self._cli_launch_requested = False

        logger.info(f"WebAppsApplication initialized (ID: {APP_ID})")

    def do_startup(self) -> None:
        """Application startup - initialize components."""
        Adw.Application.do_startup(self)

        logger.info("Application starting up...")

        # Initialize core components
        self._init_components()

        # Setup actions
        self._setup_actions()

        # Setup keyboard shortcuts
        self._setup_shortcuts()

        logger.info("Application startup complete")

    def _init_components(self) -> None:
        """Initialize core application components."""
        # Initialize database
        db_path = XDGDirectories.get_database_path()
        self.database = Database(db_path)
        logger.info(f"Database initialized: {db_path}")

        # Initialize profile manager
        self.profile_manager = ProfileManager()
        logger.info("ProfileManager initialized")

        # Initialize webapp manager
        self.webapp_manager = WebAppManager(self.database, self.profile_manager)
        logger.info("WebAppManager initialized")
        self.app_settings = self.database.get_app_settings()
        selected_language = set_language(self.app_settings.language)
        logger.debug("Idioma configurado: %s", selected_language)
        self._refresh_desktop_entries()

    def _refresh_desktop_entries(self) -> None:
        """Ensure desktop launchers are up to date for existing webapps."""
        if not self.webapp_manager:
            return

        webapps = self.webapp_manager.get_all_webapps()
        for webapp in webapps:
            try:
                DesktopIntegration.update_desktop_file(webapp)
            except Exception as e:
                logger.warning(
                    "Failed to refresh desktop entry for %s: %s", webapp.id, e
                )

    def update_language(self, language: str) -> None:
        """Persist and apply language changes."""
        selected = set_language(language)
        if not self.database:
            return

        if not self.app_settings:
            self.app_settings = AppSettings(language=selected)
        else:
            self.app_settings.language = selected

        try:
            self.database.update_app_settings(self.app_settings)
        except Exception as exc:
            logger.error("Failed to persist language change: %s", exc)

    def _setup_actions(self) -> None:
        """Setup application actions."""
        # Preferences action
        preferences_action = Gio.SimpleAction.new("preferences", None)
        preferences_action.connect("activate", self._on_preferences_action)
        self.add_action(preferences_action)

        # About action
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about_action)
        self.add_action(about_action)

        # Quit action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self._on_quit_action)
        self.add_action(quit_action)

        logger.debug("Actions setup complete")

    def _setup_shortcuts(self) -> None:
        """Setup keyboard shortcuts."""
        self.set_accels_for_action("app.quit", ["<Ctrl>Q"])
        self.set_accels_for_action("app.preferences", ["<Ctrl>comma"])
        self.set_accels_for_action("window.close", ["<Ctrl>W"])

        logger.debug("Keyboard shortcuts setup complete")

    def do_activate(self) -> None:
        """Application activation - create and show main window."""
        logger.info("Application activated")

        # Create main window if it doesn't exist
        if not self.main_window:
            self.main_window = MainWindow(
                application=self,
                webapp_manager=self.webapp_manager,
                profile_manager=self.profile_manager,
            )

        # Present window unless suppressed (e.g., CLI webapp launch)
        if self._suppress_main_window:
            logger.debug("Main window presentation suppressed for CLI launch")
        else:
            self.main_window.present()

        # Reset suppression flag after each activation
        self._suppress_main_window = False

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> int:
        """Handle command line arguments.

        Args:
            command_line: Command line object

        Returns:
            Exit code (0 for success)
        """
        logger.debug("Processing command line arguments")

        # Skip binary name (argv[0])
        argv = list(command_line.get_arguments())[1:]
        cli_options = self._parse_command_line_args(argv)

        if cli_options.webapp_id and not cli_options.show_main_window:
            self._suppress_main_window = True
            self._cli_launch_requested = True
        else:
            self._cli_launch_requested = False

        # Activate application (show main window unless suppressed)
        self.activate()

        if cli_options.webapp_id:
            if not self.main_window:
                logger.error("Main window not available to launch webapp")
            else:
                GLib.idle_add(
                    self._launch_webapp_from_cli,
                    cli_options.webapp_id,
                    cli_options.new_window,
                    priority=GLib.PRIORITY_DEFAULT,
                )

        if cli_options.show_preferences:
            GLib.idle_add(
                self._show_preferences_dialog,
                priority=GLib.PRIORITY_DEFAULT,
            )

        return 0

    def _parse_command_line_args(self, args: list[str]) -> _CLIOptions:
        """Parse command line arguments from CLI or .desktop files."""
        parser = argparse.ArgumentParser(
            prog="webapps-manager", add_help=False, allow_abbrev=False
        )
        parser.add_argument("--webapp", dest="webapp_id")
        parser.add_argument("--new-window", action="store_true")
        parser.add_argument("--preferences", action="store_true")
        parser.add_argument("--show-main-window", action="store_true")

        try:
            namespace, _ = parser.parse_known_args(args)
        except SystemExit:
            logger.warning("Failed to parse command line args: %s", args)
            return _CLIOptions()

        return _CLIOptions(
            webapp_id=namespace.webapp_id,
            new_window=namespace.new_window,
            show_preferences=namespace.preferences,
            show_main_window=namespace.show_main_window,
        )

    def _launch_webapp_from_cli(self, webapp_id: str, new_window: bool) -> bool:
        """Launch webapp requested via command line."""
        if not self.main_window:
            logger.error("Cannot launch webapp %s: main window not initialised", webapp_id)
            return GLib.SOURCE_REMOVE

        logger.debug(
            "Launching webapp %s from CLI (new_window=%s)",
            webapp_id,
            new_window,
        )

        window = self.main_window.launch_webapp(webapp_id)

        if self._cli_launch_requested and window is not None:
            self._cli_launch_requested = False
            window.connect("destroy", self._on_cli_window_destroy)

        return GLib.SOURCE_REMOVE

    def _on_cli_window_destroy(self, window: Gtk.Window) -> None:
        """Ensure application exits after CLI-launched window closes."""
        logger.debug("CLI-launched webapp window closed; quitting application")
        self.quit()

    def _show_preferences_dialog(self) -> bool:
        """Show preferences dialog (used by CLI and action)."""
        if not self.main_window:
            self.activate()

        if not self.main_window:
            return GLib.SOURCE_REMOVE

        dialog = PreferencesDialog(self.main_window, self)
        dialog.present()
        return GLib.SOURCE_REMOVE

    def _on_preferences_action(
        self, action: Gio.SimpleAction, parameter: Optional[GLib.Variant]
    ) -> None:
        """Handle preferences action.

        Args:
            action: Action that was triggered
            parameter: Optional action parameter
        """
        logger.info("Preferences action triggered")
        self._show_preferences_dialog()

    def _on_about_action(
        self, action: Gio.SimpleAction, parameter: Optional[GLib.Variant]
    ) -> None:
        """Handle about action.

        Args:
            action: Action that was triggered
            parameter: Optional action parameter
        """
        logger.info("About action triggered")

        about = Adw.AboutDialog()
        about.set_application_name(_("about.title"))
        about.set_application_icon(APP_ID)
        about.set_version("1.0.0")
        about.set_developer_name("Bruno Vaz")
        about.set_license_type(Gtk.License.GPL_3_0)
        about.set_comments(_("about.description"))
        about.set_website("https://github.com/yourusername/webapps-manager")
        about.set_issue_url("https://github.com/yourusername/webapps-manager/issues")

        about.set_developers(["Bruno Vaz"])
        about.set_copyright("© 2025 Bruno Vaz")

        about.present(self.main_window)

    def _on_quit_action(
        self, action: Gio.SimpleAction, parameter: Optional[GLib.Variant]
    ) -> None:
        """Handle quit action.

        Args:
            action: Action that was triggered
            parameter: Optional action parameter
        """
        logger.info("Quit action triggered")
        self.quit()

    def do_shutdown(self) -> None:
        """Application shutdown - cleanup resources."""
        logger.info("Application shutting down...")

        # Close database connection
        if self.database:
            self.database.close()
            logger.debug("Database connection closed")

        Adw.Application.do_shutdown(self)

        logger.info("Application shutdown complete")
