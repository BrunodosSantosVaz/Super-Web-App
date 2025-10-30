"""Desktop environment integration.

This module handles creation of .desktop files for launcher integration
and other desktop environment integration features.
"""

import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PIL import Image

from ..data.models import WebApp
from ..utils.logger import get_logger
from ..utils.xdg import (
    APP_ID,
    XDGDirectories,
    build_app_instance_id,
    build_icon_filename,
)

logger = get_logger(__name__)


class DesktopIntegration:
    """Handles desktop environment integration.

    Creates and manages .desktop files for system launcher integration.
    """

    @staticmethod
    def create_desktop_file(webapp: WebApp) -> Optional[Path]:
        """Create .desktop file for a webapp.

        Args:
            webapp: WebApp to create desktop file for

        Returns:
            Path to created .desktop file, or None if failed
        """
        logger.info(f"Creating .desktop file for webapp: {webapp.name}")

        desktop_file_path = XDGDirectories.get_desktop_file_path(webapp.id)

        try:
            # Install webapp icon to system icons directory
            DesktopIntegration._install_webapp_icon(webapp)

            content = DesktopIntegration._generate_desktop_content(webapp)

            with open(desktop_file_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Make executable
            desktop_file_path.chmod(0o755)

            # Sync copy to desktop folder (optional)
            DesktopIntegration._copy_to_user_desktop(desktop_file_path, webapp.id)

            # Update desktop database
            DesktopIntegration._update_desktop_database()

            logger.info(f"Desktop file created: {desktop_file_path}")
            return desktop_file_path

        except Exception as e:
            logger.error(f"Failed to create desktop file: {e}", exc_info=True)
            return None

    @staticmethod
    def _generate_desktop_content(webapp: WebApp) -> str:
        """Generate .desktop file content.

        Args:
            webapp: WebApp to generate content for

        Returns:
            Desktop file content as string
        """
        # Use icon name (will be looked up in system icons)
        # Format: br.com.infinity.webapps.{webapp_id}
        app_instance_id = build_app_instance_id(webapp.id)
        icon_name = app_instance_id
        if not webapp.icon_path or not Path(webapp.icon_path).exists():
            icon_name = "applications-internet"  # Default icon

        # Get category for .desktop file
        desktop_category = DesktopIntegration._get_desktop_category(webapp.category)

        exec_cmd = DesktopIntegration._build_exec_command(webapp.id)

        content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name={webapp.name}
Comment=Access to {webapp.name}
Icon={icon_name}
Exec={exec_cmd}
Terminal=false
Categories={desktop_category}
Keywords=webapp;browser;internet;{webapp.name.lower()};
StartupWMClass={app_instance_id}
StartupNotify=true
"""
        return content

    @staticmethod
    def _build_exec_command(webapp_id: str) -> str:
        """Build executable command for desktop entry."""
        if XDGDirectories.is_flatpak():
            return f"flatpak run {APP_ID} --webapp {webapp_id}"

        script_path = DesktopIntegration._ensure_launcher_script(webapp_id)
        return shlex.quote(str(script_path))

    @staticmethod
    def _get_desktop_category(category: Optional[str]) -> str:
        """Map webapp category to .desktop Categories.

        Args:
            category: WebApp category ID

        Returns:
            Desktop file Categories string
        """
        category_map = {
            "social": "Network;Chat;",
            "messaging": "Network;InstantMessaging;",
            "productivity": "Office;Productivity;",
            "entertainment": "AudioVideo;Video;",
            "news": "News;",
            "development": "Development;",
            "finance": "Finance;",
        }

        return category_map.get(category or "other", "Network;WebBrowser;")

    @staticmethod
    def _install_webapp_icon(webapp: WebApp) -> None:
        """Install webapp icon to system icons directory.

        Args:
            webapp: WebApp with icon to install
        """
        if not webapp.icon_path or not Path(webapp.icon_path).exists():
            logger.debug(f"No icon to install for webapp {webapp.id}")
            return

        try:
            DesktopIntegration._remove_webapp_icon(webapp.id)
            base_icon_path = Path(webapp.icon_path)
            if not base_icon_path.exists():
                logger.warning("Icon source missing for %s", webapp.id)
                return

            icon_name = build_icon_filename(webapp.id)
            icon_base_dir = Path.home() / ".local" / "share" / "icons" / "hicolor"

            try:
                source_image = Image.open(base_icon_path)
                if source_image.mode not in ("RGB", "RGBA"):
                    source_image = source_image.convert("RGBA")

                for size in (48, 64, 128):
                    size_dir = icon_base_dir / f"{size}x{size}" / "apps"
                    size_dir.mkdir(parents=True, exist_ok=True)
                    destination = size_dir / icon_name
                    resized = source_image.copy()
                    resized.thumbnail((size, size), Image.Resampling.LANCZOS)
                    resized.save(destination, "PNG", optimize=True)
                    logger.debug("Webapp icon installed: %s", destination)
            except Exception as exc:
                logger.warning("Failed to process icon %s: %s", base_icon_path, exc)
                fallback_dir = icon_base_dir / "48x48" / "apps"
                fallback_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(base_icon_path, fallback_dir / icon_name)
                logger.debug("Fallback copy for icon installed: %s", fallback_dir / icon_name)

            # Update icon cache
            try:
                subprocess.run(
                    ['gtk-update-icon-cache', '-f', '-t', str(icon_base_dir)],
                    check=False,
                    capture_output=True,
                )
            except Exception as e:
                logger.debug(f"Could not update icon cache: {e}")

        except Exception as e:
            logger.warning(f"Failed to install webapp icon: {e}")

    @staticmethod
    def _copy_to_user_desktop(desktop_file_path: Path, webapp_id: str) -> None:
        """Copy desktop entry to user's desktop folder if available."""
        desktop_shortcut = XDGDirectories.get_user_desktop_file_path(webapp_id)
        if not desktop_shortcut:
            logger.debug("User desktop directory unavailable; skipping desktop shortcut")
            return

        try:
            shutil.copy2(desktop_file_path, desktop_shortcut)
            desktop_shortcut.chmod(0o755)
            try:
                subprocess.run(
                    ["gio", "set", str(desktop_shortcut), "metadata::trusted", "true"],
                    check=False,
                    capture_output=True,
                )
            except FileNotFoundError:
                logger.debug("gio command not available; skipping trust metadata")
            logger.debug(f"Desktop shortcut synced: {desktop_shortcut}")
        except Exception as e:
            logger.warning(f"Failed to sync desktop shortcut: {e}")

    @staticmethod
    def _remove_user_desktop_shortcut(webapp_id: str) -> None:
        """Remove desktop shortcut from user's desktop folder."""
        desktop_shortcut = XDGDirectories.get_user_desktop_file_path(webapp_id)
        legacy_shortcut = None
        if desktop_shortcut:
            legacy_shortcut = desktop_shortcut.parent / f"{APP_ID}.{webapp_id}.desktop"

        for shortcut in (desktop_shortcut, legacy_shortcut):
            if shortcut and shortcut.exists():
                try:
                    shortcut.unlink()
                    logger.debug("Desktop shortcut removed: %s", shortcut)
                except Exception as e:
                    logger.warning("Failed to remove desktop shortcut %s: %s", shortcut, e)

    @staticmethod
    def delete_desktop_file(webapp_id: str) -> None:
        """Delete .desktop file for a webapp.

        Args:
            webapp_id: WebApp ID
        """
        logger.info(f"Deleting .desktop file for webapp: {webapp_id}")

        desktop_file_path = XDGDirectories.get_desktop_file_path(webapp_id)
        legacy_desktop_file_path = (
            XDGDirectories.get_applications_dir() / f"{APP_ID}.{webapp_id}.desktop"
        )

        desktop_removed = False
        if desktop_file_path.exists():
            desktop_file_path.unlink()
            desktop_removed = True
            logger.debug(f"Desktop file deleted: {desktop_file_path}")
        if legacy_desktop_file_path.exists() and legacy_desktop_file_path != desktop_file_path:
            legacy_desktop_file_path.unlink()
            desktop_removed = True
            logger.debug("Legacy desktop file deleted: %s", legacy_desktop_file_path)
        if desktop_removed:
            DesktopIntegration._update_desktop_database()

        DesktopIntegration._remove_user_desktop_shortcut(webapp_id)
        DesktopIntegration._remove_launcher_script(webapp_id)
        DesktopIntegration._remove_webapp_icon(webapp_id)

    @staticmethod
    def update_desktop_file(webapp: WebApp) -> None:
        """Update existing .desktop file.

        Args:
            webapp: WebApp with updated information
        """
        logger.debug(f"Updating .desktop file for webapp: {webapp.name}")
        DesktopIntegration.delete_desktop_file(webapp.id)
        DesktopIntegration.create_desktop_file(webapp)

    @staticmethod
    def _update_desktop_database() -> None:
        """Update desktop database after changes.

        This makes the new/updated launcher entries appear immediately.
        """
        try:
            subprocess.run(
                [
                    "update-desktop-database",
                    "-q",
                    str(XDGDirectories.get_applications_dir()),
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.debug("Desktop database updated")
        except Exception as e:
            logger.warning(f"Failed to update desktop database: {e}")

    @staticmethod
    def _ensure_launcher_script(webapp_id: str) -> Path:
        """Create or update helper script used for launching webapps."""
        script_path = XDGDirectories.get_launcher_script_path(webapp_id)
        project_root = Path(__file__).resolve().parents[2]

        python_executable = sys.executable or shutil.which("python3") or "python3"
        project_root_str = str(project_root).replace('"', '\\"')
        python_exec_str = str(python_executable).replace('"', '\\"')

        content = f"""#!/bin/sh
PROJECT_ROOT="{project_root_str}"
PYTHON_EXEC="{python_exec_str}"

cd "$PROJECT_ROOT" || exit 1
PYTHONPATH="$PROJECT_ROOT" exec "$PYTHON_EXEC" -m app.standalone_webapp {webapp_id} "$@"
"""
        script_path.write_text(content, encoding="utf-8")
        script_path.chmod(0o755)
        logger.debug(f"Launcher script prepared: {script_path}")
        return script_path

    @staticmethod
    def _remove_launcher_script(webapp_id: str) -> None:
        """Remove helper launcher script if it exists."""
        script_path = XDGDirectories.get_launcher_script_path(webapp_id)
        if script_path.exists():
            try:
                script_path.unlink()
                logger.debug(f"Launcher script removed: {script_path}")
            except Exception as e:
                logger.warning(f"Failed to remove launcher script: {e}")

    @staticmethod
    def _remove_webapp_icon(webapp_id: str) -> None:
        """Remove webapp icon from system icons directory.

        Args:
            webapp_id: WebApp ID
        """
        try:
            icon_base_dir = Path.home() / '.local' / 'share' / 'icons' / 'hicolor'
            removed_any = False

            icon_names = {build_icon_filename(webapp_id), f"{APP_ID}.{webapp_id}.png"}

            for size_dir in icon_base_dir.glob("*x*/apps"):
                for icon_name in icon_names:
                    icon_path = size_dir / icon_name
                    if icon_path.exists():
                        icon_path.unlink()
                        removed_any = True
                        logger.debug("Webapp icon removed: %s", icon_path)

            if removed_any:
                try:
                    subprocess.run(
                        ['gtk-update-icon-cache', '-f', '-t', str(icon_base_dir)],
                        check=False,
                        capture_output=True,
                    )
                except Exception as e:
                    logger.debug(f"Could not update icon cache: {e}")

        except Exception as e:
            logger.warning(f"Failed to remove webapp icon: {e}")
