"""Simple internationalization utilities.

This module loads translation strings from the user configuration
directory and provides helpers to translate UI labels at runtime.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, Optional

from .logger import get_logger
from .xdg import XDGDirectories

logger = get_logger(__name__)


_DEFAULT_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "pt": {
        "app.title": "WebApps Manager",
        "menu.preferences": "Preferências",
        "menu.about": "Sobre",
        "menu.quit": "Sair",
        "main.new_webapp": "Novo WebApp",
        "main.search_placeholder": "Pesquisar webapps...",
        "main.status.title": "Nenhum WebApp",
        "main.status.description": "Crie seu primeiro webapp para começar",
        "main.launch.tooltip": "Abrir WebApp",
        "main.settings.tooltip": "Configurações",
        "main.delete.tooltip": "Excluir WebApp",
        "dialog.new_title": "Novo WebApp",
        "dialog.edit_title": "Editar WebApp",
        "dialog.cancel": "Cancelar",
        "dialog.create": "Criar",
        "dialog.save": "Salvar",
        "dialog.group.basic": "Informações Básicas",
        "dialog.field.name": "Nome",
        "dialog.field.url": "URL",
        "dialog.field.category": "Categoria",
        "dialog.group.icon": "Ícone",
        "dialog.icon.fetch_auto": "Buscar ícone automaticamente",
        "dialog.icon.fetch_button": "Buscar ícone",
        "dialog.icon.fetch_loading": "Buscando...",
        "dialog.icon.fetch_success": "Ícone buscado ✓",
        "dialog.icon.fetch_failure": "Não foi possível buscar o ícone",
        "dialog.icon.fetch_error": "Erro ao buscar ícone",
        "dialog.group.navigation": "Navegação",
        "dialog.navigation.allow_tabs": "Permitir múltiplas abas",
        "dialog.navigation.allow_tabs_desc": "Ativa navegação por abas neste webapp",
        "dialog.navigation.allow_popups": "Permitir janelas popup",
        "dialog.navigation.allow_popups_desc": "Autoriza este webapp a abrir popups",
        "dialog.group.system": "Integração com o sistema",
        "dialog.system.allow_notifications": "Permitir notificações",
        "dialog.system.allow_notifications_desc": "Autoriza este webapp a exibir notificações",
        "dialog.system.show_tray": "Mostrar na bandeja",
        "dialog.system.show_tray_desc": "Exibe ícone na bandeja enquanto estiver aberto",
        "icon.fetch.title": "Buscar Ícone",
        "webapp.back.tooltip": "Voltar",
        "webapp.forward.tooltip": "Avançar",
        "webapp.reload.tooltip": "Recarregar",
        "webapp.tab.loading": "Carregando...",
        "webapp.popup.title": "Popup",
        "preferences.title": "Preferências",
        "preferences.general": "Geral",
        "preferences.language": "Idioma",
        "preferences.language.subtitle": "Selecione o idioma da interface",
        "preferences.language.pt": "Português",
        "preferences.language.en": "Inglês",
        "tray.open": "Abrir",
        "tray.quit": "Sair",
        "category.social": "Social",
        "category.messaging": "Mensagens",
        "category.productivity": "Produtividade",
        "category.entertainment": "Entretenimento",
        "category.news": "Notícias",
        "category.development": "Desenvolvimento",
        "category.finance": "Finanças",
        "category.other": "Outros",
        "about.title": "WebApps Manager",
        "about.description": "Transforme sites em aplicativos de desktop com perfis isolados e integração nativa.",
        "about.website": "Site",
        "about.issues": "Relatar problemas",
    },
    "en": {
        "app.title": "WebApps Manager",
        "menu.preferences": "Preferences",
        "menu.about": "About",
        "menu.quit": "Quit",
        "main.new_webapp": "New WebApp",
        "main.search_placeholder": "Search webapps...",
        "main.status.title": "No WebApps",
        "main.status.description": "Create your first webapp to get started",
        "main.launch.tooltip": "Launch WebApp",
        "main.settings.tooltip": "Settings",
        "main.delete.tooltip": "Delete WebApp",
        "dialog.new_title": "New WebApp",
        "dialog.edit_title": "Edit WebApp",
        "dialog.cancel": "Cancel",
        "dialog.create": "Create",
        "dialog.save": "Save",
        "dialog.group.basic": "Basic Information",
        "dialog.field.name": "Name",
        "dialog.field.url": "URL",
        "dialog.field.category": "Category",
        "dialog.group.icon": "Icon",
        "dialog.icon.fetch_auto": "Fetch icon automatically",
        "dialog.icon.fetch_button": "Fetch icon",
        "dialog.icon.fetch_loading": "Fetching...",
        "dialog.icon.fetch_success": "Icon fetched ✓",
        "dialog.icon.fetch_failure": "Failed to fetch icon",
        "dialog.icon.fetch_error": "Error fetching icon",
        "dialog.group.navigation": "Navigation",
        "dialog.navigation.allow_tabs": "Allow multiple tabs",
        "dialog.navigation.allow_tabs_desc": "Enable tabbed browsing within this webapp",
        "dialog.navigation.allow_popups": "Allow popup windows",
        "dialog.navigation.allow_popups_desc": "Allow this webapp to open popup windows",
        "dialog.group.system": "System integration",
        "dialog.system.allow_notifications": "Allow notifications",
        "dialog.system.allow_notifications_desc": "Allow this webapp to show notifications",
        "dialog.system.show_tray": "Show in system tray",
        "dialog.system.show_tray_desc": "Show icon in system tray when running",
        "icon.fetch.title": "Fetch Icon",
        "webapp.back.tooltip": "Go back",
        "webapp.forward.tooltip": "Go forward",
        "webapp.reload.tooltip": "Reload",
        "webapp.tab.loading": "Loading...",
        "webapp.popup.title": "Popup",
        "preferences.title": "Preferences",
        "preferences.general": "General",
        "preferences.language": "Language",
        "preferences.language.subtitle": "Select the interface language",
        "preferences.language.pt": "Portuguese",
        "preferences.language.en": "English",
        "tray.open": "Open",
        "tray.quit": "Quit",
        "category.social": "Social",
        "category.messaging": "Messaging",
        "category.productivity": "Productivity",
        "category.entertainment": "Entertainment",
        "category.news": "News",
        "category.development": "Development",
        "category.finance": "Finance",
        "category.other": "Other",
        "about.title": "WebApps Manager",
        "about.description": "Turn websites into desktop apps with isolated profiles and native integration.",
        "about.website": "Website",
        "about.issues": "Report issues",
    },
}

_CONFIG_FILENAME = "translations.json"
_translations: Dict[str, Dict[str, str]] = {}
_current_language = "pt"
_listeners: set[Callable[[str], None]] = set()


def _config_path() -> Path:
    return XDGDirectories.get_config_dir() / _CONFIG_FILENAME


def _ensure_config_file(path: Path) -> None:
    if path.exists():
        return
    try:
        path.write_text(
            json.dumps(_DEFAULT_TRANSLATIONS, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.debug("Arquivo de traduções criado em %s", path)
    except Exception as exc:
        logger.warning("Não foi possível criar arquivo de traduções: %s", exc)


def _load_translations() -> None:
    global _translations
    path = _config_path()
    _ensure_config_file(path)

    data: Dict[str, Dict[str, str]] = {
        lang: entries.copy() for lang, entries in _DEFAULT_TRANSLATIONS.items()
    }

    if path.exists():
        try:
            user_data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(user_data, dict):
                for lang, entries in user_data.items():
                    if not isinstance(entries, dict):
                        continue
                    base = data.setdefault(lang, {})
                    base.update({str(k): str(v) for k, v in entries.items()})
        except Exception as exc:
            logger.warning("Falha ao ler traduções personalizadas: %s", exc)

    _translations = data


def available_languages() -> Dict[str, str]:
    """Return available languages with their localized labels."""
    return {
        "pt": _translations.get("pt", {}).get("preferences.language.pt", "Português"),
        "en": _translations.get("en", {}).get("preferences.language.en", "English"),
    }


def subscribe(callback: Callable[[str], None]) -> Callable[[str], None]:
    """Subscribe to language change notifications."""
    _listeners.add(callback)
    return callback


def unsubscribe(callback: Callable[[str], None]) -> None:
    """Unsubscribe from language change notifications."""
    _listeners.discard(callback)


def set_language(language: str) -> str:
    """Set current language (falls back to Portuguese)."""
    global _current_language
    if language not in _translations:
        language = "pt"
    if language == _current_language:
        return language

    _current_language = language
    for listener in list(_listeners):
        try:
            listener(language)
        except Exception as exc:
            logger.debug("Erro ao notificar listener de idioma: %s", exc)
    return language


def get_language() -> str:
    """Return current language code."""
    return _current_language


def gettext(key: str, *, language: Optional[str] = None, default: Optional[str] = None, **fmt) -> str:
    """Get translated string for key."""
    lang = language or _current_language
    fallback_lang = "pt"

    value = (
        _translations.get(lang, {}).get(
            key, _translations.get(fallback_lang, {}).get(key, default or key)
        )
    )

    if fmt:
        try:
            value = value.format(**fmt)
        except Exception as exc:
            logger.debug("Erro formatando string %s: %s", key, exc)
    return value


def get_category_label(category_id: str) -> str:
    """Return localized label for a category identifier."""
    return gettext(
        f"category.{category_id}",
        default=category_id.capitalize(),
    )


# Initialize translations on module import
_load_translations()
