from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from typing import Any

DEFAULT_MENU_ID = "default"
MENU_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,48}$")
MAX_SECTIONS = 24
MAX_ITEMS_PER_SECTION = 64
MAX_TOTAL_ITEMS = 256


class MenuValidationError(ValueError):
    """Raised when a menu payload cannot be accepted."""


DEFAULT_STYLE: dict[str, Any] = {
    "theme": "aurora",
    "primary_color": "#7c3aed",
    "background_color": "#f8fafc",
    "card_color": "#ffffff",
    "text_color": "#111827",
    "muted_color": "#6b7280",
    "radius": 24,
    "width": 900,
    "show_updated_at": True,
}

DEFAULT_MENU: dict[str, Any] = {
    "id": DEFAULT_MENU_ID,
    "name": "默认菜单",
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
    title = _clean_text(raw.get("title"), "title", default=name, max_length=120)
    subtitle = _clean_text(raw.get("subtitle"), "subtitle", default="", max_length=240)
    footer = _clean_text(raw.get("footer"), "footer", default="", max_length=240)
    style = _normalize_style(raw.get("style"))
    sections = _normalize_sections(raw.get("sections"))
    created_at = _clean_text(raw.get("created_at"), "created_at", default=_now_iso(), max_length=64)
    updated_at = _clean_text(raw.get("updated_at"), "updated_at", default=_now_iso(), max_length=64)

    return {
        "id": menu_id,
        "name": name,
        "title": title,
        "subtitle": subtitle,
        "footer": footer,
        "style": style,
        "sections": sections,
        "created_at": created_at,
        "updated_at": updated_at,
    }


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
        style[key] = _clean_text(style.get(key), key, default=DEFAULT_STYLE[key], max_length=32)

    style["radius"] = _clamp_int(style.get("radius"), default=24, minimum=0, maximum=48)
    style["width"] = _clamp_int(style.get("width"), default=900, minimum=520, maximum=1400)
    style["show_updated_at"] = bool(style.get("show_updated_at", True))
    return style


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
        "enabled": bool(raw_item.get("enabled", True)),
    }


def _clean_text(value: Any, field_name: str, *, default: str = "", max_length: int) -> str:
    if value is None:
        value = default
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    if len(value) > max_length:
        raise MenuValidationError(f"{field_name} is too long")
    return value


def _clamp_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
