"""Dialog for adding/editing webapps.

This module provides a dialog for creating new webapps or editing
existing ones with all configuration options.
"""

from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from ..core.desktop_integration import DesktopIntegration
from ..core.icon_fetcher import IconFetcher
from ..core.webapp_manager import WebAppManager
from ..data.models import DEFAULT_CATEGORIES, WebApp
from ..utils.i18n import (
    gettext as _,
    get_category_label,
    subscribe as i18n_subscribe,
    unsubscribe as i18n_unsubscribe,
)
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AddWebAppDialog(Adw.Dialog):
    """Dialog for adding a new webapp."""

    def __init__(
        self,
        parent: Gtk.Window,
        webapp_manager: WebAppManager,
        webapp: Optional[WebApp] = None,
        on_saved=None,
    ) -> None:
        """Initialize add webapp dialog.

        Args:
            parent: Parent window
            webapp_manager: WebAppManager for creating webapp
            webapp: Optional WebApp to edit (None for new)
            on_saved: Optional callback to call after successfully saving
        """
        super().__init__()

        self.webapp_manager = webapp_manager
        self.webapp = webapp
        self.icon_fetcher = IconFetcher()
        self.fetched_icon_path: Optional[str] = None
        self.on_saved = on_saved
        self._is_edit = webapp is not None
        self._icon_button_status = "default"
        self._language_subscription = None
        self._language_subscription = i18n_subscribe(self._on_language_changed)

        self.set_title(_("dialog.edit_title") if self._is_edit else _("dialog.new_title"))
        self.set_content_width(600)
        self.set_content_height(700)

        self._build_ui()

        if webapp:
            self._load_webapp_data()

        self._apply_translations()
        self.connect("destroy", self._on_destroy)

        logger.debug("AddWebAppDialog initialized")

    def _build_ui(self) -> None:
        """Build dialog UI."""
        # Main content box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(24)
        content_box.set_margin_bottom(24)
        content_box.set_margin_start(24)
        content_box.set_margin_end(24)

        # Toolbar header
        header = Adw.HeaderBar()
        header.add_css_class("flat")

        # Cancel button
        cancel_button = Gtk.Button()
        cancel_button.connect("clicked", lambda b: self.close())
        header.pack_start(cancel_button)
        self.cancel_button = cancel_button

        # Create/Save button
        self.save_button = Gtk.Button()
        self.save_button.add_css_class("suggested-action")
        self.save_button.connect("clicked", self._on_save_clicked)
        header.pack_end(self.save_button)

        # Basic information group
        basic_group = Adw.PreferencesGroup()
        self.basic_group = basic_group

        # Name entry
        self.name_entry = Adw.EntryRow()
        self.name_entry.connect("changed", self._on_input_changed)
        basic_group.add(self.name_entry)

        # URL entry
        self.url_entry = Adw.EntryRow()
        self.url_entry.connect("changed", self._on_input_changed)
        basic_group.add(self.url_entry)

        # Category dropdown
        category_row = Adw.ComboRow()
        self.category_row = category_row

        # Create string list for categories
        self.categories_list = Gtk.StringList()
        for cat in DEFAULT_CATEGORIES:
            self.categories_list.append(get_category_label(cat.id))

        category_row.set_model(self.categories_list)
        category_row.set_selected(0)
        basic_group.add(category_row)

        content_box.append(basic_group)

        # Icon group
        icon_group = Adw.PreferencesGroup()
        self.icon_group = icon_group

        icon_button_row = Adw.ActionRow()
        self.icon_button_row = icon_button_row

        fetch_icon_button = Gtk.Button()
        fetch_icon_button.connect("clicked", self._on_fetch_icon_clicked)
        icon_button_row.add_suffix(fetch_icon_button)
        self.fetch_icon_button = fetch_icon_button

        icon_group.add(icon_button_row)
        content_box.append(icon_group)

        # Navigation group
        nav_group = Adw.PreferencesGroup()
        self.nav_group = nav_group

        # Allow tabs
        self.tabs_switch = Adw.SwitchRow()
        self.tabs_switch.set_active(True)
        nav_group.add(self.tabs_switch)

        # Allow popups
        self.popups_switch = Adw.SwitchRow()
        self.popups_switch.set_active(True)
        nav_group.add(self.popups_switch)

        content_box.append(nav_group)

        # System integration group
        system_group = Adw.PreferencesGroup()
        self.system_group = system_group

        # Notifications
        self.notif_switch = Adw.SwitchRow()
        self.notif_switch.set_active(True)
        system_group.add(self.notif_switch)

        # Show in tray
        self.tray_switch = Adw.SwitchRow()
        self.tray_switch.set_active(False)
        system_group.add(self.tray_switch)


        content_box.append(system_group)

        # Scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(content_box)
        scrolled.set_vexpand(True)

        # Toolbar view
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(scrolled)

        self.set_child(toolbar_view)

    def _apply_translations(self) -> None:
        """Apply localized strings to widgets."""
        self.set_title(_("dialog.edit_title") if self._is_edit else _("dialog.new_title"))
        self.cancel_button.set_label(_("dialog.cancel"))
        self.save_button.set_label(_("dialog.save") if self._is_edit else _("dialog.create"))
        self.basic_group.set_title(_("dialog.group.basic"))
        self.name_entry.set_title(_("dialog.field.name"))
        self.url_entry.set_title(_("dialog.field.url"))
        self.category_row.set_title(_("dialog.field.category"))
        self.icon_group.set_title(_("dialog.group.icon"))
        self.icon_button_row.set_title(_("dialog.icon.fetch_auto"))
        status_map = {
            "default": _("dialog.icon.fetch_button"),
            "loading": _("dialog.icon.fetch_loading"),
            "success": _("dialog.icon.fetch_success"),
            "failure": _("dialog.icon.fetch_failure"),
            "error": _("dialog.icon.fetch_error"),
        }
        self.fetch_icon_button.set_label(status_map.get(self._icon_button_status, _("dialog.icon.fetch_button")))
        self.nav_group.set_title(_("dialog.group.navigation"))
        self.tabs_switch.set_title(_("dialog.navigation.allow_tabs"))
        self.tabs_switch.set_subtitle(_("dialog.navigation.allow_tabs_desc"))
        self.popups_switch.set_title(_("dialog.navigation.allow_popups"))
        self.popups_switch.set_subtitle(_("dialog.navigation.allow_popups_desc"))
        self.system_group.set_title(_("dialog.group.system"))
        self.notif_switch.set_title(_("dialog.system.allow_notifications"))
        self.notif_switch.set_subtitle(_("dialog.system.allow_notifications_desc"))
        self.tray_switch.set_title(_("dialog.system.show_tray"))
        self.tray_switch.set_subtitle(_("dialog.system.show_tray_desc"))

        selected = self.category_row.get_selected()
        self.categories_list = Gtk.StringList()
        for cat in DEFAULT_CATEGORIES:
            self.categories_list.append(get_category_label(cat.id))
        self.category_row.set_model(self.categories_list)
        if 0 <= selected < self.categories_list.get_n_items():
            self.category_row.set_selected(selected)
        else:
            self.category_row.set_selected(0)

    def _load_webapp_data(self) -> None:
        """Load webapp data into form (for editing)."""
        if not self.webapp:
            return

        self.name_entry.set_text(self.webapp.name)
        self.url_entry.set_text(self.webapp.url)

        # Find and set category
        if self.webapp.category:
            for i, cat in enumerate(DEFAULT_CATEGORIES):
                if cat.id == self.webapp.category:
                    self.category_row.set_selected(i)
                    break

        # Load settings
        settings = self.webapp_manager.get_webapp_settings(self.webapp.id)
        if settings:
            self.tabs_switch.set_active(settings.allow_tabs)
            self.popups_switch.set_active(settings.allow_popups)
            self.notif_switch.set_active(settings.enable_notif)
            self.tray_switch.set_active(settings.show_tray)

    def _on_language_changed(self, _language: str) -> None:
        """React to global language changes."""
        self._apply_translations()

    def _on_destroy(self, *_args) -> None:
        """Cleanup translation listeners on destroy."""
        if self._language_subscription:
            i18n_unsubscribe(self._language_subscription)

    def _on_input_changed(self, entry: Adw.EntryRow) -> None:
        """Handle input changed.

        Args:
            entry: Entry that changed
        """
        # Enable save button only if name and URL are filled
        name = self.name_entry.get_text().strip()
        url = self.url_entry.get_text().strip()

        self.save_button.set_sensitive(len(name) > 0 and len(url) > 0)

    def _on_fetch_icon_clicked(self, button: Gtk.Button) -> None:
        """Handle fetch icon button clicked.

        Args:
            button: Button widget
        """
        url = self.url_entry.get_text().strip()

        if not url:
            logger.warning("Cannot fetch icon: no URL provided")
            return

        logger.info(f"Fetching icon for URL: {url}")

        # Show loading state
        button.set_sensitive(False)
        self._icon_button_status = "loading"
        button.set_label(_("dialog.icon.fetch_loading"))

        # TODO: Run in background thread to avoid blocking UI
        # For now, fetch synchronously
        try:
            # Generate temporary ID for icon fetching
            temp_id = "temp"
            icon_path = self.icon_fetcher.fetch_icon(url, temp_id)

            if icon_path:
                self.fetched_icon_path = str(icon_path)
                self._icon_button_status = "success"
                button.set_label(_("dialog.icon.fetch_success"))
                logger.info("Icon fetched successfully")
            else:
                self._icon_button_status = "failure"
                button.set_label(_("dialog.icon.fetch_failure"))
                logger.warning("Failed to fetch icon")

        except Exception as e:
            logger.error(f"Error fetching icon: {e}", exc_info=True)
            self._icon_button_status = "error"
            button.set_label(_("dialog.icon.fetch_error"))

        finally:
            button.set_sensitive(True)

    def _on_save_clicked(self, button: Gtk.Button) -> None:
        """Handle save button clicked.

        Args:
            button: Button widget
        """
        name = self.name_entry.get_text().strip()
        url = self.url_entry.get_text().strip()

        if not name or not url:
            logger.warning("Cannot save: name or URL is empty")
            return

        # Get selected category
        selected_index = self.category_row.get_selected()
        category = DEFAULT_CATEGORIES[selected_index].id

        try:
            if self.webapp:
                # Update existing webapp
                self.webapp_manager.update_webapp(
                    self.webapp.id,
                    name=name,
                    url=url,
                    category=category,
                    icon_path=self.fetched_icon_path,
                )

                # Update settings
                settings = self.webapp_manager.get_webapp_settings(self.webapp.id)
                if settings:
                    settings.allow_tabs = self.tabs_switch.get_active()
                    settings.allow_popups = self.popups_switch.get_active()
                    settings.enable_notif = self.notif_switch.get_active()
                    settings.show_tray = self.tray_switch.get_active()
                    self.webapp_manager.update_webapp_settings(settings)

                # Update .desktop file
                updated_webapp = self.webapp_manager.get_webapp(self.webapp.id)
                DesktopIntegration.update_desktop_file(updated_webapp)

                logger.info(f"WebApp updated: {self.webapp.id}")
            else:
                # Create new webapp
                webapp, settings = self.webapp_manager.create_webapp(
                    name, url, category
                )

                # Update settings with form values
                settings.allow_tabs = self.tabs_switch.get_active()
                settings.allow_popups = self.popups_switch.get_active()
                settings.enable_notif = self.notif_switch.get_active()
                settings.show_tray = self.tray_switch.get_active()
                self.webapp_manager.update_webapp_settings(settings)

                # If icon was fetched, update webapp with icon path
                if self.fetched_icon_path:
                    self.webapp_manager.update_webapp(
                        webapp.id, icon_path=self.fetched_icon_path
                    )
                    # Reload webapp to get updated icon path
                    webapp = self.webapp_manager.get_webapp(webapp.id)

                # Create .desktop file for launcher integration
                DesktopIntegration.create_desktop_file(webapp)

                logger.info(f"WebApp created: {webapp.id}")

            # Close dialog
            self.close()

            # Notify parent to refresh
            if self.on_saved:
                self.on_saved()

        except Exception as e:
            logger.error(f"Error saving webapp: {e}", exc_info=True)
            # TODO: Show error dialog
