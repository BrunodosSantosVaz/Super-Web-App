"""Tab manager for dynamic tab handling in WebApp windows.

This module provides the TabManager class that handles all tab-related
operations including creation, deletion, switching, and automatic resizing.
"""

from typing import Dict, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")
from gi.repository import Adw, Gtk, WebKit

from ..data.models import WebApp, WebAppSettings
from ..utils.i18n import gettext as _
from ..utils.logger import get_logger
from ..webengine.popup_handler import PopupHandler
from ..webengine.profile_manager import ProfileManager
from ..webengine.webview_manager import WebViewManager

logger = get_logger(__name__)

# Constants for tab management
MAX_TABS = 10


class TabManager:
    """Manages dynamic tabs for a WebApp window.

    This class handles:
    - Creating new tabs (up to MAX_TABS limit)
    - Closing tabs
    - Switching between tabs
    - Automatic tab width adjustment based on tab count
    - Dynamic title updates from document.title
    """

    def __init__(
        self,
        tab_view: Adw.TabView,
        tab_bar: Adw.TabBar,
        webapp: WebApp,
        settings: WebAppSettings,
        profile_manager: ProfileManager,
        webview_manager: WebViewManager,
        popup_handler: PopupHandler,
        on_title_changed_callback=None,
        on_load_changed_callback=None,
    ) -> None:
        """Initialize the TabManager.

        Args:
            tab_view: The Adw.TabView widget
            tab_bar: The Adw.TabBar widget
            webapp: WebApp configuration
            settings: WebApp settings
            profile_manager: Profile manager for creating isolated WebViews
            webview_manager: WebView manager for creating WebViews
            popup_handler: Popup handler for WebView configuration
            on_title_changed_callback: Optional callback for title changes
            on_load_changed_callback: Optional callback for load changes
        """
        self.tab_view = tab_view
        self.tab_bar = tab_bar
        self.webapp = webapp
        self.settings = settings
        self.profile_manager = profile_manager
        self.webview_manager = webview_manager
        self.popup_handler = popup_handler
        self.on_title_changed_callback = on_title_changed_callback
        self.on_load_changed_callback = on_load_changed_callback

        # Track WebViews by tab page
        self.webviews: Dict[Adw.TabPage, WebKit.WebView] = {}

        # Connect tab view signals
        self.tab_view.connect("close-page", self._on_close_page_request)
        self.tab_view.connect("page-attached", self._on_page_attached)
        self.tab_view.connect("page-detached", self._on_page_detached)

        logger.info("TabManager initialized for webapp %s", webapp.name)

    def get_tab_count(self) -> int:
        """Get the current number of open tabs.

        Returns:
            Number of tabs currently open
        """
        return self.tab_view.get_n_pages()

    def can_create_tab(self) -> bool:
        """Check if a new tab can be created.

        Returns:
            True if under the limit, False otherwise
        """
        return self.get_tab_count() < MAX_TABS

    def create_new_tab(self, uri: Optional[str] = None) -> Optional[Adw.TabPage]:
        """Create a new tab with a WebView.

        Args:
            uri: Optional URI to load. If None, uses webapp's default URL

        Returns:
            The created TabPage, or None if limit reached
        """
        if not self.can_create_tab():
            logger.warning("Cannot create tab: limit of %d reached", MAX_TABS)
            self._show_limit_reached_dialog()
            return None

        # Create new WebView
        webview = self.webview_manager.create_webview_with_popup_handler(
            webapp_id=self.webapp.id,
            settings=self.settings,
            popup_handler=self.popup_handler,
            webapp_name=self.webapp.name,
            icon_path=self.webapp.icon_path
        )

        # Connect WebView signals
        webview.connect("notify::title", self._on_webview_title_changed)
        webview.connect("notify::uri", self._on_webview_uri_changed)
        webview.connect("load-changed", self._on_webview_load_changed)

        # Add to tab view
        page = self.tab_view.append(webview)
        page.set_title(self.webapp.name)
        page.set_loading(True)

        # Store webview reference
        self.webviews[page] = webview

        # Load URI
        load_uri = uri or self.webapp.url
        webview.load_uri(load_uri)

        # Select the new tab
        self.tab_view.set_selected_page(page)

        # Update tab widths
        self._update_tab_widths()

        logger.info(
            "Created new tab (%d/%d): %s",
            self.get_tab_count(),
            MAX_TABS,
            load_uri
        )

        return page

    def close_tab(self, page: Adw.TabPage) -> bool:
        """Close a specific tab.

        Args:
            page: The TabPage to close

        Returns:
            True if closed, False otherwise
        """
        # Don't close if it's the last tab
        if self.get_tab_count() <= 1:
            # Create a new tab before closing the last one
            self.create_new_tab()

        # Remove from tracking
        if page in self.webviews:
            del self.webviews[page]

        # Close the page
        self.tab_view.close_page(page)

        # Update tab widths
        self._update_tab_widths()

        logger.info("Closed tab. Remaining tabs: %d", self.get_tab_count())
        return True

    def get_active_webview(self) -> Optional[WebKit.WebView]:
        """Get the WebView of the currently selected tab.

        Returns:
            The active WebView, or None if no tab is selected
        """
        page = self.tab_view.get_selected_page()
        if page:
            return self.webviews.get(page)
        return None

    def _update_tab_widths(self) -> None:
        """Update tab widths based on the number of open tabs.

        Note: Since expand_tabs is enabled on the TabBar, GTK automatically
        handles proportional resizing of tabs. We just log the change here.
        """
        tab_count = self.get_tab_count()
        logger.debug("Tab count changed: %d tabs (auto-resizing enabled)", tab_count)

    def _show_limit_reached_dialog(self) -> None:
        """Show dialog when tab limit is reached."""
        dialog = Adw.MessageDialog.new(
            None,  # No parent, will be transient
            _("webapp.tab.limit_reached"),
            None
        )
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")

        # Try to set transient for the window
        try:
            # Get the window from tab_view
            widget = self.tab_view
            while widget:
                if isinstance(widget, Gtk.Window):
                    dialog.set_transient_for(widget)
                    break
                widget = widget.get_parent()
        except Exception as e:
            logger.debug("Could not set dialog parent: %s", e)

        dialog.present()
        logger.debug("Showed tab limit dialog")

    def _on_webview_title_changed(
        self, webview: WebKit.WebView, param
    ) -> None:
        """Handle WebView title changes.

        Args:
            webview: The WebView whose title changed
            param: Parameter specification
        """
        title = webview.get_title()
        if not title:
            return

        # Find the page for this webview
        for page, wv in self.webviews.items():
            if wv == webview:
                page.set_title(title)
                logger.debug("Updated tab title: %s", title)
                break

        # Call external callback if provided
        if self.on_title_changed_callback:
            self.on_title_changed_callback(webview, param)

    def _on_webview_uri_changed(
        self, webview: WebKit.WebView, param
    ) -> None:
        """Handle WebView URI changes.

        Args:
            webview: The WebView whose URI changed
            param: Parameter specification
        """
        uri = webview.get_uri()
        logger.debug("Tab URI changed: %s", uri)

    def _on_webview_load_changed(
        self, webview: WebKit.WebView, load_event: WebKit.LoadEvent
    ) -> None:
        """Handle WebView load state changes.

        Args:
            webview: The WebView that changed
            load_event: Load event type
        """
        # Find the page for this webview
        for page, wv in self.webviews.items():
            if wv == webview:
                if load_event == WebKit.LoadEvent.STARTED:
                    page.set_loading(True)
                elif load_event == WebKit.LoadEvent.FINISHED:
                    page.set_loading(False)
                break

        # Call external callback if provided
        if self.on_load_changed_callback:
            self.on_load_changed_callback(webview, load_event)

    def _on_close_page_request(
        self, tab_view: Adw.TabView, page: Adw.TabPage
    ) -> bool:
        """Handle tab close request.

        Args:
            tab_view: The TabView
            page: The page being closed

        Returns:
            True to prevent close, False to allow
        """
        # If this is the last tab, create a new one first
        if self.get_tab_count() <= 1:
            self.create_new_tab()

        # Remove from tracking
        if page in self.webviews:
            del self.webviews[page]

        # Update tab widths after close
        self._update_tab_widths()

        # Allow close
        return False

    def _on_page_attached(
        self, tab_view: Adw.TabView, page: Adw.TabPage, position: int
    ) -> None:
        """Handle page attached to tab view.

        Args:
            tab_view: The TabView
            page: The page that was attached
            position: Position where it was attached
        """
        logger.debug("Tab attached at position %d", position)
        self._update_tab_widths()

    def _on_page_detached(
        self, tab_view: Adw.TabView, page: Adw.TabPage, position: int
    ) -> None:
        """Handle page detached from tab view.

        Args:
            tab_view: The TabView
            page: The page that was detached
            position: Position where it was
        """
        logger.debug("Tab detached from position %d", position)
        self._update_tab_widths()

        # If all tabs are closed, ensure at least one exists
        if self.get_tab_count() == 0:
            self.create_new_tab()

    def cleanup(self) -> None:
        """Clean up resources when TabManager is destroyed."""
        logger.info("Cleaning up TabManager")
        self.webviews.clear()
