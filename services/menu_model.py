from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from typing import Any

DEFAULT_MENU_ID = "default"
MENU_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,48}$")
HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
MAX_SECTIONS = 24
MAX_ITEMS_PER_SECTION = 64
MAX_TOTAL_ITEMS = 256
WIDTH_MODES = {"auto", "custom"}
SECTION_GAP_MODES = {"auto", "custom"}
CARD_SIZES = {"compact", "standard", "large", "banner"}
CONTENT_BLOCKS = {"command", "label", "description"}
DEFAULT_CONTENT_ORDER = ("command", "label", "description")


class MenuValidationError(ValueError):
    """Raised when a menu payload cannot be accepted."""


DEFAULT_STYLE: dict[str, Any] = {
    "theme": "aurora",
    "primary_color": "#7c3aed",
    "background_color": "#f8fafc",
    "background_image": "",
    "background_image_asset_id": "",
    "background_image_name": "",
    "background_image_x": 0,
    "background_image_y": 0,
    "background_image_width": 100,
    "background_overlay": 0,
    "background_blur": 0,
    "background_brightness": 100,
    "card_color": "#ffffff",
    "text_color": "#111827",
    "muted_color": "#6b7280",
    "font_family": "",
    "foreground_opacity": 92,
    "radius": 24,
    "width_mode": "auto",
    "width": 760,
    "columns": 2,
    "section_gap_mode": "auto",
    "section_gap": 14,
    "card_gap": 10,
    "section_padding": 15,
    "shadow_strength": 1,
    "border_strength": 1,
    "watermark": "",
    "show_updated_at": True,
}

DEFAULT_MENU: dict[str, Any] = {
    "id": DEFAULT_MENU_ID,
    "name": "默认菜单",
    "aliases": ["main"],
    "title": "Bot 功能菜单",
    "subtitle": "发送下列指令即可使用对应功能",
    "footer": "由 AstrBot 菜单插件生成",
    "style": DEFAULT_STYLE,
    "sections": [
        {
            "title": "常用功能",
            "items": [
                {
                    "label": "菜单",
                    "command": "/menu",
                    "description": "查看当前机器人功能菜单",
                    "icon": "📋",
                    "enabled": True,
                },
                {
                    "label": "帮助",
                    "command": "/help",
                    "description": "查看 AstrBot 帮助信息",
                    "icon": "❔",
                    "enabled": True,
                },
            ],
        },
        {
            "title": "管理提示",
            "items": [
                {
                    "label": "自定义菜单",
                    "command": "WebUI → 插件 → Bot 菜单",
                    "description": "在插件 Pages 页面编辑菜单并实时预览",
                    "icon": "⚙️",
                    "enabled": True,
                }
            ],
        },
    ],
}


def default_menu() -> dict[str, Any]:
    menu = copy.deepcopy(DEFAULT_MENU)
    now = _now_iso()
    menu["created_at"] = now
    menu["updated_at"] = now
    return normalize_menu(menu)


def normalize_menu(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise MenuValidationError("menu must be an object")

    menu_id = _clean_text(raw.get("id"), "id", max_length=48)
    if not menu_id or not MENU_ID_PATTERN.fullmatch(menu_id):
        raise MenuValidationError("menu id must be 1-48 chars: letters, numbers, '_' or '-'")

    name = _clean_text(raw.get("name"), "name", default=menu_id, max_length=80)
    aliases = _normalize_aliases(raw.get("aliases"), menu_id)
    title = _clean_text(raw.get("title"), "title", default=name, max_length=120)
    subtitle = _clean_text(raw.get("subtitle"), "subtitle", default="", max_length=240)
    footer = _clean_text(raw.get("footer"), "footer", default="", max_length=240)
    style = _normalize_style(raw.get("style"))
    sections = _normalize_sections(raw.get("sections"))
    render_snapshot = _normalize_render_snapshot(raw.get("render_snapshot"))
    created_at = _clean_text(raw.get("created_at"), "created_at", default=_now_iso(), max_length=64)
    updated_at = _clean_text(raw.get("updated_at"), "updated_at", default=_now_iso(), max_length=64)
    deleted_at = _clean_optional_text(raw.get("deleted_at"), "deleted_at", max_length=64)

    menu = {
        "id": menu_id,
        "name": name,
        "aliases": aliases,
        "title": title,
        "subtitle": subtitle,
        "footer": footer,
        "style": style,
        "sections": sections,
        "render_snapshot": render_snapshot,
        "created_at": created_at,
        "updated_at": updated_at,
    }
    if deleted_at:
        menu["deleted_at"] = deleted_at
    return menu


def _normalize_render_snapshot(raw_snapshot: Any) -> dict[str, Any] | None:
    if raw_snapshot in (None, ""):
        return None
    if not isinstance(raw_snapshot, dict):
        return None
    try:
        raw = copy.deepcopy(raw_snapshot)
    except Exception:
        return None
    if raw.get("renderer") != "typst-direct":
        return None
    width = _clamp_float(raw.get("width"), default=0, minimum=0, maximum=4000)
    height = _clamp_float(raw.get("height"), default=0, minimum=0, maximum=8000)
    if width <= 0 or height <= 0:
        return None
    raw["version"] = _clamp_int(raw.get("version"), default=1, minimum=1, maximum=2)
    raw["width"] = width
    raw["height"] = height
    return raw


def normalize_menu_collection(raw_menus: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_menus, list):
        raise MenuValidationError("menus must be a list")
    if not raw_menus:
        raise MenuValidationError("menus cannot be empty")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_menus:
        menu = normalize_menu(raw)
        if menu["id"] in seen:
            raise MenuValidationError(f"duplicate menu id: {menu['id']}")
        seen.add(menu["id"])
        normalized.append(menu)
    return normalized


def touch_menu(menu: dict[str, Any]) -> dict[str, Any]:
    touched = normalize_menu(menu)
    touched["updated_at"] = _now_iso()
    return touched


def _normalize_style(raw_style: Any) -> dict[str, Any]:
    style = copy.deepcopy(DEFAULT_STYLE)
    if isinstance(raw_style, dict):
        style.update(raw_style)

    style["theme"] = _clean_text(style.get("theme"), "theme", default="aurora", max_length=32)
    for key in ("primary_color", "background_color", "card_color", "text_color", "muted_color"):
        style[key] = _clean_color(style.get(key), default=DEFAULT_STYLE[key])

    style["background_image"] = _clean_background_image(style.get("background_image"))
    style["background_image_asset_id"] = _clean_text(
        style.get("background_image_asset_id"),
        "background image asset id",
        default="",
        max_length=80,
    )
    style["background_image_name"] = _clean_text(
        style.get("background_image_name"),
        "background image name",
        default="",
        max_length=160,
    )
    style["background_image_x"] = _clamp_int(style.get("background_image_x"), default=0, minimum=-300, maximum=300)
    style["background_image_y"] = _clamp_int(style.get("background_image_y"), default=0, minimum=-300, maximum=300)
    style["background_image_width"] = _clamp_int(style.get("background_image_width"), default=100, minimum=10, maximum=600)
    style["background_overlay"] = _clamp_int(style.get("background_overlay"), default=0, minimum=0, maximum=100)
    style["background_blur"] = _clamp_int(style.get("background_blur"), default=0, minimum=0, maximum=40)
    style["background_brightness"] = _clamp_int(style.get("background_brightness"), default=100, minimum=20, maximum=200)
    style["font_family"] = _clean_text(style.get("font_family"), "font family", default="", max_length=120)
    style["foreground_opacity"] = _clamp_int(style.get("foreground_opacity"), default=92, minimum=0, maximum=100)
    style["radius"] = _clamp_int(style.get("radius"), default=24, minimum=0, maximum=48)
    style["width_mode"] = _clean_choice(style.get("width_mode"), WIDTH_MODES, default="auto")
    style["width"] = _clamp_int(style.get("width"), default=760, minimum=520, maximum=1400)
    style["columns"] = _clamp_int(style.get("columns"), default=2, minimum=1, maximum=4)
    style["section_gap_mode"] = _clean_choice(style.get("section_gap_mode"), SECTION_GAP_MODES, default="auto")
    style["section_gap"] = _clamp_int(style.get("section_gap"), default=14, minimum=0, maximum=200)
    style["card_gap"] = _clamp_int(style.get("card_gap"), default=10, minimum=0, maximum=60)
    style["section_padding"] = _clamp_int(style.get("section_padding"), default=15, minimum=0, maximum=80)
    style["shadow_strength"] = _clamp_int(style.get("shadow_strength"), default=1, minimum=0, maximum=5)
    style["border_strength"] = _clamp_int(style.get("border_strength"), default=1, minimum=0, maximum=5)
    style["watermark"] = _clean_text(style.get("watermark"), "watermark", default="", max_length=80)
    style["show_updated_at"] = bool(style.get("show_updated_at", True))
    return style


def _normalize_aliases(raw_aliases: Any, menu_id: str) -> list[str]:
    if raw_aliases in (None, ""):
        return []
    if isinstance(raw_aliases, str):
        raw_values = [raw_aliases]
    elif isinstance(raw_aliases, list):
        raw_values = raw_aliases
    else:
        raise MenuValidationError("aliases must be a list of strings")

    aliases: list[str] = []
    seen = {menu_id.casefold()}
    for raw_alias in raw_values:
        alias = _clean_text(raw_alias, "alias", default="", max_length=48)
        if not alias:
            continue
        folded = alias.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        aliases.append(alias)
    if len(aliases) > 16:
        raise MenuValidationError("menu can contain at most 16 aliases")
    return aliases


def _normalize_sections(raw_sections: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_sections, list) or not raw_sections:
        raise MenuValidationError("menu must contain at least one section")
    if len(raw_sections) > MAX_SECTIONS:
        raise MenuValidationError(f"menu can contain at most {MAX_SECTIONS} sections")

    sections: list[dict[str, Any]] = []
    total_items = 0
    for index, raw_section in enumerate(raw_sections, start=1):
        if not isinstance(raw_section, dict):
            raise MenuValidationError(f"section #{index} must be an object")
        title = _clean_text(raw_section.get("title"), "section title", default=f"分组 {index}", max_length=80)
        raw_items = raw_section.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            raise MenuValidationError(f"section '{title}' must contain at least one item")
        if len(raw_items) > MAX_ITEMS_PER_SECTION:
            raise MenuValidationError(f"section '{title}' has too many items")
        items = [_normalize_item(item, title, idx) for idx, item in enumerate(raw_items, start=1)]
        total_items += len(items)
        sections.append({"title": title, "items": items})

    if total_items > MAX_TOTAL_ITEMS:
        raise MenuValidationError(f"menu can contain at most {MAX_TOTAL_ITEMS} items")
    return sections


def _normalize_item(raw_item: Any, section_title: str, index: int) -> dict[str, Any]:
    if not isinstance(raw_item, dict):
        raise MenuValidationError(f"item #{index} in '{section_title}' must be an object")
    label = _clean_text(raw_item.get("label"), "item label", max_length=80)
    if not label:
        raise MenuValidationError(f"item #{index} in '{section_title}' requires a label")
    return {
        "label": label,
        "command": _clean_text(raw_item.get("command"), "item command", default="", max_length=120),
        "description": _clean_text(raw_item.get("description"), "item description", default="", max_length=240),
        "icon": _clean_text(raw_item.get("icon"), "item icon", default="", max_length=12),
        "card_size": _clean_choice(raw_item.get("card_size"), CARD_SIZES, default="standard"),
        "enabled": bool(raw_item.get("enabled", True)),
        **_normalize_item_layout(raw_item),
    }


def _normalize_item_layout(raw_item: dict[str, Any]) -> dict[str, Any]:
    layout: dict[str, Any] = {}
    if "content_order" in raw_item:
        layout["content_order"] = _normalize_content_order(raw_item.get("content_order"))
    if "content_gap" in raw_item:
        layout["content_gap"] = _clamp_int(raw_item.get("content_gap"), default=2, minimum=0, maximum=40)
    for key, default, minimum, maximum in (
        ("command_font_size", 14, 8, 34),
        ("label_font_size", 11.5, 8, 30),
        ("description_font_size", 11.5, 8, 28),
    ):
        if key in raw_item:
            layout[key] = _clamp_float(raw_item.get(key), default=default, minimum=minimum, maximum=maximum)
    return layout


def _normalize_content_order(raw_order: Any) -> list[str]:
    if isinstance(raw_order, str):
        values = [part.strip() for part in raw_order.split(",")]
    elif isinstance(raw_order, list):
        values = [str(part).strip() for part in raw_order]
    else:
        values = []
    order: list[str] = []
    for value in values:
        if value in CONTENT_BLOCKS and value not in order:
            order.append(value)
    for value in DEFAULT_CONTENT_ORDER:
        if value not in order:
            order.append(value)
    return order[:3]


def _clean_text(value: Any, field_name: str, *, default: str = "", max_length: int) -> str:
    if value is None:
        value = default
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    if len(value) > max_length:
        raise MenuValidationError(f"{field_name} is too long")
    return value


def _clean_optional_text(value: Any, field_name: str, *, max_length: int) -> str:
    if value in (None, ""):
        return ""
    return _clean_text(value, field_name, default="", max_length=max_length)


def _clean_color(value: Any, *, default: str) -> str:
    raw = _clean_text(value, "color", default=default, max_length=32)
    return raw if HEX_COLOR_PATTERN.fullmatch(raw) else default


def _clean_background_image(value: Any) -> str:
    if not value:
        return ""
    raw = str(value).strip()
    if raw.startswith(("data:image/", "http://", "https://")):
        return raw
    return ""


def _clean_choice(value: Any, choices: set[str], *, default: str) -> str:
    raw = _clean_text(value, "choice", default=default, max_length=32).lower()
    return raw if raw in choices else default


def _clamp_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _clamp_float(value: Any, *, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    parsed = max(minimum, min(maximum, parsed))
    return round(parsed * 2) / 2


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
