"""Bot menu plugin service layer."""

from .menu_model import DEFAULT_MENU_ID, MenuValidationError, normalize_menu
from .asset_storage import AssetStorage
from .fonts import FontRegistry
from .history_storage import MenuHistoryStorage
from .renderer import build_preview_html, build_render_payload, preview_width_for_menu
from .render_cache import MenuRenderCache
from .render_coordinator import MenuRenderCoordinator
from .routing_storage import RoutingStorage
from .storage import MenuStorage
from .typst_renderer import build_typst_document, materialize_saved_preview_raster, render_menu_via_typst

__all__ = [
    "AssetStorage",
    "DEFAULT_MENU_ID",
    "FontRegistry",
    "MenuHistoryStorage",
    "MenuRenderCache",
    "MenuRenderCoordinator",
    "MenuStorage",
    "MenuValidationError",
    "RoutingStorage",
    "build_render_payload",
    "build_preview_html",
    "build_typst_document",
    "materialize_saved_preview_raster",
    "normalize_menu",
    "preview_width_for_menu",
    "render_menu_via_typst",
]
