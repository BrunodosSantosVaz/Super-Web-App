"""Preferences dialog implementation."""

from __future__ import annotations

from typing import List

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from ..utils.i18n import (
    available_languages,
    gettext as _,
    subscribe as i18n_subscribe,
    unsubscribe as i18n_unsubscribe,
)


class PreferencesDialog(Adw.PreferencesWindow):
    """Application preferences window."""

    def __init__(self, parent: Adw.ApplicationWindow, application) -> None:
        super().__init__(title=_("preferences.title"))

        self._application = application
        self._language_codes: List[str] = []
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(420, 260)

        self._language_subscription = None
        self._language_subscription = i18n_subscribe(self._on_language_changed)

        self._build_ui()
        self._apply_translations()

        self.connect("destroy", self._on_destroy)

    def _build_ui(self) -> None:
        """Build preferences layout."""
        page = Adw.PreferencesPage()

        general_group = Adw.PreferencesGroup()
        self.general_group = general_group

        self.language_row = Adw.ComboRow()
        self.language_row.connect("notify::selected", self._on_language_row_changed)
        general_group.add(self.language_row)

        page.add(general_group)
        self.add(page)

    def _populate_languages(self) -> None:
        """Populate language combo with available options."""
        languages = available_languages()
        codes = list(languages.keys())
        labels = [languages[code] for code in codes]

        selected_code = getattr(self._application.app_settings, "language", "pt")
        selected_index = codes.index(selected_code) if selected_code in codes else 0

        string_list = Gtk.StringList()
        for label in labels:
            string_list.append(label)

        self._language_codes = codes
        self.language_row.set_model(string_list)
        self.language_row.set_selected(selected_index)

    def _apply_translations(self) -> None:
        """Update strings when language changes."""
        self.set_title(_("preferences.title"))
        self.general_group.set_title(_("preferences.general"))
        self.language_row.set_title(_("preferences.language"))
        self.language_row.set_subtitle(_("preferences.language.subtitle"))
        self._populate_languages()

    def _on_language_row_changed(self, *_args) -> None:
        """Handle language selection change."""
        selected = self.language_row.get_selected()
        if selected < 0 or selected >= len(self._language_codes):
            return

        language_code = self._language_codes[selected]
        current = getattr(self._application.app_settings, "language", "pt")
        if language_code == current:
            return

        self._application.update_language(language_code)

    def _on_language_changed(self, _language: str) -> None:
        """React to global language updates."""
        self._apply_translations()

    def _on_destroy(self, *_args) -> None:
        """Cleanup language subscription."""
        if self._language_subscription:
            i18n_unsubscribe(self._language_subscription)
