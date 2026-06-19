"""Bot menu plugin service layer."""

from .menu_model import DEFAULT_MENU_ID, MenuValidationError, normalize_menu
from .local_image import image_file_to_data_url, render_menu_image, render_menu_via_browser
from .renderer import build_preview_html, build_render_payload, preview_width_for_menu
from .render_cache import MenuRenderCache
from .render_coordinator import MenuRenderCoordinator
from .storage import MenuStorage

__all__ = [
    "DEFAULT_MENU_ID",
    "MenuRenderCache",
    "MenuRenderCoordinator",
    "MenuStorage",
    "MenuValidationError",
    "build_render_payload",
    "build_preview_html",
    "image_file_to_data_url",
    "normalize_menu",
    "preview_width_for_menu",
    "render_menu_image",
    "render_menu_via_browser",
]
