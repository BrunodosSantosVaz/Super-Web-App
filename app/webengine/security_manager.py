"""Security configuration for WebKit.

This module provides security policies and configurations
to ensure safe browsing within webapps.
"""

import gi

gi.require_version("WebKit", "6.0")
from gi.repository import WebKit

from ..utils.logger import get_logger

logger = get_logger(__name__)


def _safe_call(obj, method: str, *args) -> None:
    """Call attribute if available, logging when not supported."""
    fn = getattr(obj, method, None)
    if callable(fn):
        try:
            fn(*args)
        except Exception as exc:
            logger.debug("Método %s falhou: %s", method, exc)
    else:
        logger.debug("Método %s indisponível nesta versão do WebKit", method)


class SecurityManager:
    """Manages security policies for WebKit WebViews."""

    @staticmethod
    def configure_webview_security(webview: WebKit.WebView) -> None:
        """Apply security configuration to a WebView.

        Args:
            webview: WebView to configure
        """
        settings = webview.get_settings()

        logger.debug("Applying security configuration to WebView")

        # Enable JavaScript (required for modern webapps)
        # Can be disabled per-webapp in settings
        _safe_call(settings, "set_enable_javascript", True)

        # Disable developer tools in production
        _safe_call(settings, "set_enable_developer_extras", False)

        # Enable page cache for performance
        _safe_call(settings, "set_enable_page_cache", True)

        # Block mixed content (HTTPS pages loading HTTP resources)
        _safe_call(settings, "set_allow_mixed_content", False)

        # Disable file access from file URLs (security)
        _safe_call(settings, "set_allow_file_access_from_file_urls", False)
        _safe_call(settings, "set_allow_universal_access_from_file_urls", False)

        # Enable WebGL (needed for many modern apps)
        _safe_call(settings, "set_enable_webgl", True)

        # Enable WebAudio
        _safe_call(settings, "set_enable_webaudio", True)

        # Disable legacy plugins (Flash, Java, etc)
        _safe_call(settings, "set_enable_plugins", False)

        # Enable media support
        _safe_call(settings, "set_enable_media_stream", True)  # WebRTC
        _safe_call(settings, "set_enable_encrypted_media", True)  # DRM
        _safe_call(settings, "set_enable_media_capabilities", True)

        # Enable modern web features
        _safe_call(settings, "set_enable_mediasource", True)
        _safe_call(settings, "set_enable_html5_database", True)
        _safe_call(settings, "set_enable_html5_local_storage", True)

        # Hardware acceleration
        policy_enum = getattr(WebKit, "HardwareAccelerationPolicy", None)
        if policy_enum is not None:
            policy_value = getattr(policy_enum, "ON_DEMAND", None)
            if policy_value is not None:
                _safe_call(
                    settings,
                    "set_hardware_acceleration_policy",
                    policy_value,
                )
            else:
                logger.debug(
                    "Valor ON_DEMAND indisponível em HardwareAccelerationPolicy"
                )
        else:
            logger.debug("Enum HardwareAccelerationPolicy não disponível no WebKit atual")

        # Enable DNS prefetching for performance
        _safe_call(settings, "set_enable_dns_prefetching", True)

        # Enable smooth scrolling
        _safe_call(settings, "set_enable_smooth_scrolling", True)

        # Enable fullscreen API
        _safe_call(settings, "set_enable_fullscreen", True)

        # Enable back/forward navigation gestures
        _safe_call(settings, "set_enable_back_forward_navigation_gestures", True)

        logger.debug("Security configuration applied")

    @staticmethod
    def configure_context_security(context: WebKit.WebContext) -> None:
        """Apply security configuration to WebContext.

        Args:
            context: WebContext to configure
        """
        logger.debug("Applying security configuration to WebContext")

        # Strict TLS policy (fail on certificate errors)
        _safe_call(context, "set_tls_errors_policy", WebKit.TLSErrorsPolicy.FAIL)

        # Enable spell checking
        _safe_call(context, "set_spell_checking_enabled", True)

        # Enable sandbox if available
        try:
            context.set_sandbox_enabled(True)
            logger.debug("Sandbox enabled")
        except Exception as e:
            logger.warning(f"Sandbox not available: {e}")

        logger.debug("Context security configuration applied")

    @staticmethod
    def is_url_safe(url: str) -> bool:
        """Check if URL is safe to load.

        Args:
            url: URL to check

        Returns:
            True if URL is safe, False otherwise
        """
        if not url:
            return False

        # Block dangerous schemes
        dangerous_schemes = ["file://", "javascript:", "data:", "about:"]
        url_lower = url.lower()

        for scheme in dangerous_schemes:
            if url_lower.startswith(scheme):
                logger.warning(f"Blocked dangerous URL scheme: {scheme}")
                return False

        return True

    @staticmethod
    def sanitize_url(url: str) -> str:
        """Sanitize URL before loading.

        Args:
            url: URL to sanitize

        Returns:
            Sanitized URL
        """
        # Remove leading/trailing whitespace
        url = url.strip()

        # Add https:// if no scheme
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        return url
