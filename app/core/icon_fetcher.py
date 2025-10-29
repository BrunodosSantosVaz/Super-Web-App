"""Automatic favicon fetching and processing.

This module handles automatic icon detection and download from websites,
with fallback strategies and image processing.
"""

import io
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image

from ..utils.logger import get_logger
from ..utils.xdg import XDGDirectories

logger = get_logger(__name__)


class IconFetcher:
    """Fetches and processes webapp icons automatically.

    Tries multiple strategies to find the best icon:
    1. Parse HTML for <link rel="icon">
    2. Try /favicon.ico
    3. Try Apple Touch Icon
    4. Use fallback generic icon
    """

    DEFAULT_TIMEOUT = 10  # seconds
    ICON_SIZE = 128  # pixels (for resizing)

    def __init__(self) -> None:
        """Initialize icon fetcher."""
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )
        logger.debug("IconFetcher initialized")

    def fetch_icon(self, url: str, webapp_id: str) -> Optional[Path]:
        """Fetch and save icon for a webapp.

        Args:
            url: Website URL to fetch icon from
            webapp_id: WebApp ID (for saving icon)

        Returns:
            Path to saved icon file, or None if failed
        """
        logger.info(f"Fetching icon for URL: {url}")

        try:
            # Strategy 1: Parse HTML for icon links
            icon_url = self._find_icon_in_html(url)

            # Strategy 2: Try /favicon.ico
            if not icon_url:
                icon_url = self._try_favicon_ico(url)

            # Strategy 3: Try Apple Touch Icon
            if not icon_url:
                icon_url = self._try_apple_touch_icon(url)

            if not icon_url:
                logger.warning(f"No icon found for {url}")
                return None

            # Download and process icon
            icon_data = self._download_icon(icon_url)
            if not icon_data:
                return None

            # Save icon
            icon_path = self._save_icon(icon_data, webapp_id)
            logger.info(f"Icon saved successfully: {icon_path}")
            return icon_path

        except Exception as e:
            logger.error(f"Failed to fetch icon: {e}", exc_info=True)
            return None

    def _find_icon_in_html(self, url: str) -> Optional[str]:
        """Find icon URL by parsing HTML.

        Args:
            url: Website URL

        Returns:
            Icon URL if found, None otherwise
        """
        try:
            response = self.session.get(url, timeout=self.DEFAULT_TIMEOUT)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Try different icon link types in order of preference
            icon_rels = [
                "icon",
                "shortcut icon",
                "apple-touch-icon",
                "apple-touch-icon-precomposed",
            ]

            for rel in icon_rels:
                link = soup.find("link", rel=lambda r: r and rel in r.lower())
                if link and link.get("href"):
                    icon_url = urljoin(url, link["href"])
                    logger.debug(f"Found icon in HTML: {icon_url}")
                    return icon_url

        except Exception as e:
            logger.debug(f"Failed to parse HTML: {e}")

        return None

    def _try_favicon_ico(self, url: str) -> Optional[str]:
        """Try to find /favicon.ico.

        Args:
            url: Website URL

        Returns:
            Icon URL if exists, None otherwise
        """
        try:
            parsed = urlparse(url)
            favicon_url = f"{parsed.scheme}://{parsed.netloc}/favicon.ico"

            response = self.session.head(favicon_url, timeout=self.DEFAULT_TIMEOUT)
            if response.status_code == 200:
                logger.debug(f"Found favicon.ico: {favicon_url}")
                return favicon_url

        except Exception as e:
            logger.debug(f"favicon.ico not found: {e}")

        return None

    def _try_apple_touch_icon(self, url: str) -> Optional[str]:
        """Try to find Apple Touch Icon.

        Args:
            url: Website URL

        Returns:
            Icon URL if exists, None otherwise
        """
        try:
            parsed = urlparse(url)
            apple_icon_url = f"{parsed.scheme}://{parsed.netloc}/apple-touch-icon.png"

            response = self.session.head(apple_icon_url, timeout=self.DEFAULT_TIMEOUT)
            if response.status_code == 200:
                logger.debug(f"Found Apple Touch Icon: {apple_icon_url}")
                return apple_icon_url

        except Exception as e:
            logger.debug(f"Apple Touch Icon not found: {e}")

        return None

    def _download_icon(self, icon_url: str) -> Optional[bytes]:
        """Download icon data.

        Args:
            icon_url: URL of icon to download

        Returns:
            Icon data as bytes, or None if failed
        """
        try:
            response = self.session.get(icon_url, timeout=self.DEFAULT_TIMEOUT)
            response.raise_for_status()

            logger.debug(f"Downloaded icon: {len(response.content)} bytes")
            return response.content

        except Exception as e:
            logger.error(f"Failed to download icon: {e}")
            return None

    def _save_icon(self, icon_data: bytes, webapp_id: str) -> Path:
        """Process and save icon.

        Args:
            icon_data: Raw icon data
            webapp_id: WebApp ID for filename

        Returns:
            Path to saved icon file

        Raises:
            Exception: If processing or saving fails
        """
        # Open image
        image = Image.open(io.BytesIO(icon_data))

        # Convert to RGBA (handles transparency)
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA")

        # Resize to standard size
        image.thumbnail((self.ICON_SIZE, self.ICON_SIZE), Image.Resampling.LANCZOS)

        # Save as PNG
        icon_path = XDGDirectories.get_icon_path(webapp_id, "png")
        image.save(icon_path, "PNG", optimize=True)

        logger.debug(f"Icon processed and saved: {icon_path}")
        return icon_path

    def close(self) -> None:
        """Close HTTP session."""
        self.session.close()
        logger.debug("IconFetcher session closed")
