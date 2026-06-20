from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any

CARD_SIZE_WIDTHS = {
    "compact": 190,
    "standard": 230,
    "large": 285,
    "banner": 360,
}
CARD_SIZE_VALUES = set(CARD_SIZE_WIDTHS)
CONTENT_BLOCKS = {"command", "label", "description"}
DEFAULT_CONTENT_ORDER = ("command", "label", "description")

# The actual image renderer and the Page preview intentionally share the same
# HTML builder. Keeping a second template here caused saved Page settings to
# diverge from the rendered /menu image.


def build_render_payload(menu: dict[str, Any], *, default_width: int = 900) -> tuple[str, dict[str, Any], dict[str, Any]]:
    options = {
        "type": "png",
        "full_page": True,
        "omit_background": False,
        "animations": "disabled",
    }
    return build_preview_html(menu, default_width=default_width), {}, options


def build_preview_html(menu: dict[str, Any], *, default_width: int = 900) -> str:
    style = _normalized_style(menu, default_width=default_width)
    width = preview_width_for_menu(menu, default_width=default_width)
    section_gap = _section_gap_for_menu(menu, style)
    sections = "\n".join(_render_preview_section(section) for section in menu.get("sections", []))
    footer_status = "" if style["show_updated_at"] is False else "实时预览"
    foreground_opacity = style["foreground_opacity"] / 100
    style_attr = (
        f"--preview-primary:{style['primary_color']};"
        f"--preview-bg:{style['background_color']};"
        f"--preview-card:{style['card_color']};"
        f"--preview-text:{style['text_color']};"
        f"--preview-muted:{style['muted_color']};"
        f"--preview-radius:{style['radius'] or 24}px;"
        f"--preview-font-family:{_css_font_family(style['font_family'])};"
        f"--preview-width:{width}px;"
        f"--preview-columns:{style['columns']};"
        f"--preview-section-gap:{section_gap}px;"
        f"--preview-card-gap:{style['card_gap']}px;"
        f"--preview-section-padding:{style['section_padding']}px;"
        f"--preview-shadow-strength:{style['shadow_strength']};"
        f"--preview-border-strength:{style['border_strength']};"
        f"--preview-bg-overlay:{style['background_overlay'] / 100:.3f};"
        f"--preview-bg-blur:{style['background_blur']}px;"
        f"--preview-bg-brightness:{style['background_brightness'] / 100:.3f};"
        f"--preview-foreground-opacity:{foreground_opacity:.3f}"
    )
    background_markup = ""
    if style["background_image"]:
        background_markup = (
            '<img class="preview-bg-image" alt="" '
            f'src="{_escape(style["background_image"])}" '
            f'style="left:{style["background_image_x"]}%;'
            f'top:{style["background_image_y"]}%;'
            f'width:{style["background_image_width"]}%;" />'
        )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <style>
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; background: transparent; }}
    body {{
      width: {width}px;
      font-family: Inter, "PingFang SC", "Microsoft YaHei", sans-serif;
      color: #0f172a;
    }}
    h1, h2, p {{ margin-top: 0; }}
    .kicker {{ margin-bottom: 6px; color: var(--primary, #7c3aed); font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: .12em; }}
    .preview-card {{
      width: var(--preview-width, 760px);
      margin: auto;
      padding: 24px;
      border-radius: var(--preview-radius, 24px);
      color: var(--preview-text, #111827);
      font-family: var(--preview-font-family, Inter, "PingFang SC", "Microsoft YaHei", sans-serif);
      background: radial-gradient(circle at top left, color-mix(in srgb, var(--preview-primary, #7c3aed), transparent 70%), transparent 35%), var(--preview-bg, #f8fafc);
      text-rendering: geometricPrecision;
      -webkit-font-smoothing: antialiased;
      position: relative;
      overflow: hidden;
      box-shadow: 0 calc(16px + var(--preview-shadow-strength, 1) * 10px) calc(40px + var(--preview-shadow-strength, 1) * 50px) rgba(15,23,42,calc(.08 + var(--preview-shadow-strength, 1) * .07));
    }}
    .preview-bg-image {{
      position: absolute;
      z-index: 0;
      max-width: none;
      height: auto;
      user-select: none;
      pointer-events: none;
      filter: blur(var(--preview-bg-blur, 0)) brightness(var(--preview-bg-brightness, 1));
    }}
    .preview-bg-overlay {{ position: absolute; inset: 0; z-index: 0; pointer-events: none; background: rgba(15,23,42,var(--preview-bg-overlay,0)); }}
    .preview-card .kicker {{ color: var(--preview-primary, #7c3aed); }}
    .preview-inner {{ position: relative; z-index: 1; padding: 22px; border-radius: inherit; background: rgba(255,255,255,var(--preview-foreground-opacity, .92)); box-shadow: 0 16px 34px rgba(15,23,42,.10); border: calc(var(--preview-border-strength, 1) * 1px) solid rgba(148,163,184,.18); }}
    .preview-title {{ margin: 12px 0 4px; font-size: 34px; line-height: 1.1; }}
    .preview-sections {{ display: grid; gap: var(--preview-section-gap, 14px); margin-top: var(--preview-section-gap, 14px); }}
    .preview-section {{ padding: var(--preview-section-padding, 15px); border-radius: 18px; background: color-mix(in srgb, var(--preview-card, #fff) calc(var(--preview-foreground-opacity, .92) * 100%), transparent); border: calc(var(--preview-border-strength, 1) * 1px) solid rgba(148,163,184,.16); }}
    .preview-items {{ display: grid; grid-template-columns: repeat(var(--preview-columns, 2), minmax(0, 1fr)); gap: var(--preview-card-gap, 10px); }}
    .preview-item {{ display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: 10px; min-height: 78px; padding: 11px; border-radius: 13px; background: rgba(241,245,249,var(--preview-foreground-opacity, .94)); }}
    .preview-item.size-compact {{ grid-template-columns: 28px minmax(0, 1fr); min-height: 66px; padding: 8px; gap: 8px; }}
    .preview-item.size-large {{ grid-template-columns: 42px minmax(0, 1fr); min-height: 112px; padding: 14px; }}
    .preview-item.size-banner {{ grid-column: 1 / -1; grid-template-columns: 46px minmax(0, 1fr); min-height: 118px; padding: 16px; }}
    .preview-item.disabled {{ opacity: .45; }}
    .preview-icon {{ line-height: 1.1; font-size: 22px; display: flex; align-items: flex-start; justify-content: center; padding-top: 1px; }}
    .preview-item-main {{ min-width: 0; display: flex; flex-direction: column; gap: var(--item-content-gap, 2px); }}
    .preview-item-title {{ display: block; margin-top: 0; color: var(--preview-text, #111827); font-size: var(--item-command-size, 14px); line-height: 1.18; letter-spacing: -.01em; overflow-wrap: anywhere; }}
    .preview-command-title {{ margin-top: 0; color: var(--preview-primary, #7c3aed); font-family: Consolas, monospace; font-weight: 800; }}
    .preview-item-name {{ color: var(--preview-text, #111827); font-size: var(--item-label-size, 11.5px); line-height: 1.28; font-weight: 650; overflow-wrap: anywhere; }}
    .preview-desc {{ margin-top: 0; padding-top: 0; color: var(--preview-muted, #6b7280); font-size: var(--item-description-size, 11.5px); line-height: 1.34; overflow-wrap: anywhere; }}
    .preview-command {{ color: var(--preview-primary, #7c3aed); font-family: Consolas, monospace; font-size: 11.5px; line-height: 1.25; overflow-wrap: anywhere; }}
    .preview-item.size-compact .preview-icon {{ font-size: 18px; }}
    .preview-item.size-large .preview-icon, .preview-item.size-banner .preview-icon {{ font-size: 26px; }}
    .preview-item.size-large .preview-command, .preview-item.size-banner .preview-command {{ font-size: 12px; }}
    .preview-sub, .preview-footer {{ color: var(--preview-muted, #6b7280); }}
    .preview-footer {{ display: flex; justify-content: space-between; margin-top: 16px; font-size: 12px; }}
    .preview-watermark {{ position: absolute; right: 22px; bottom: 16px; z-index: 2; pointer-events: none; color: var(--preview-muted); opacity: .24; font-size: 38px; font-weight: 900; transform: rotate(-8deg); }}
  </style>
</head>
<body>
  <div class="preview-card" style="{style_attr}">
    {background_markup}
    <div class="preview-bg-overlay"></div>
    <div class="preview-inner">
      <div class="kicker">📋 {_escape(menu.get("name") or menu.get("id"))}</div>
      <h1 class="preview-title">{_escape(menu.get("title") or "Bot 功能菜单")}</h1>
      <div class="preview-sub">{_escape(menu.get("subtitle") or "")}</div>
      <div class="preview-sections">
      {sections}
      </div>
      <div class="preview-footer"><span>{_escape(menu.get("footer") or "")}</span><span>{footer_status}</span></div>
    </div>
    {f'<div class="preview-watermark">{_escape(style["watermark"])}</div>' if style["watermark"] else ''}
  </div>
</body>
</html>
"""


def _render_preview_section(section: dict[str, Any]) -> str:
    items = "\n".join(_render_preview_item(item) for item in section.get("items", []))
    return f"""<section class="preview-section">
        <h3>{_escape(section.get("title") or "分组")}</h3>
        <div class="preview-items">
          {items}
        </div>
      </section>"""


def _render_preview_item(item: dict[str, Any]) -> str:
    disabled = " disabled" if item.get("enabled") is False else ""
    size = _card_size(item.get("card_size"))
    style_attr = _item_preview_style(item)
    blocks = "".join(_render_item_content_block(item, block) for block in _content_order(item))
    return f"""<div class="preview-item size-{size}{disabled}" style="{style_attr}">
            <div class="preview-icon">{_escape(item.get("icon") or "•")}</div>
            <div class="preview-item-main">{blocks}</div>
          </div>"""


def _render_item_content_block(item: dict[str, Any], block: str) -> str:
    if block == "command":
        return f'<strong class="preview-item-title preview-command-title">{_escape(item.get("command") or "")}</strong>'
    if block == "label":
        return f'<div class="preview-item-name">{_escape(item.get("label") or "未命名")}</div>'
    return f'<div class="preview-desc">{_escape(item.get("description") or "")}</div>'


def preview_width_for_menu(menu: dict[str, Any], *, default_width: int = 900) -> int:
    style = _normalized_style(menu, default_width=default_width)
    if style["width_mode"] == "custom":
        return style["width"]

    columns = style["columns"]
    desired_card_width = 190
    for section in menu.get("sections", []):
        for item in section.get("items", []):
            size = _card_size(item.get("card_size"))
            text_units = max(
                len(str(item.get("label") or "")),
                len(str(item.get("command") or "")),
                len(str(item.get("description") or "")) // 2,
            )
            desired_card_width = max(desired_card_width, CARD_SIZE_WIDTHS[size], 150 + min(150, text_units * 6))

    content_ch = max(
        len(str(menu.get("title") or "")),
        len(str(menu.get("subtitle") or "")) // 2,
        *(len(str(section.get("title") or "")) for section in menu.get("sections", [])),
        0,
    )
    chrome_width = 24 * 2 + 22 * 2 + 15 * 2
    grid_width = columns * desired_card_width + max(0, columns - 1) * 10
    title_width = 260 + min(260, content_ch * 10)
    return _clamp_int(max(grid_width + chrome_width, title_width), default=default_width, minimum=520, maximum=1200)


def _normalized_style(menu: dict[str, Any], *, default_width: int) -> dict[str, Any]:
    style = menu.get("style") if isinstance(menu.get("style"), dict) else {}
    width_mode = str(style.get("width_mode") or "auto").strip().lower()
    if width_mode not in {"auto", "custom"}:
        width_mode = "auto"
    section_gap_mode = str(style.get("section_gap_mode") or "auto").strip().lower()
    if section_gap_mode not in {"auto", "custom"}:
        section_gap_mode = "auto"
    return {
        "primary_color": style.get("primary_color") or "#7c3aed",
        "background_color": style.get("background_color") or "#f8fafc",
        "background_image": style.get("background_image") or "",
        "background_image_name": style.get("background_image_name") or "",
        "background_image_x": _clamp_int(style.get("background_image_x"), default=0, minimum=-300, maximum=300),
        "background_image_y": _clamp_int(style.get("background_image_y"), default=0, minimum=-300, maximum=300),
        "background_image_width": _clamp_int(style.get("background_image_width"), default=100, minimum=10, maximum=600),
        "background_overlay": _clamp_int(style.get("background_overlay"), default=0, minimum=0, maximum=100),
        "background_blur": _clamp_int(style.get("background_blur"), default=0, minimum=0, maximum=40),
        "background_brightness": _clamp_int(style.get("background_brightness"), default=100, minimum=20, maximum=200),
        "card_color": style.get("card_color") or "#ffffff",
        "text_color": style.get("text_color") or "#111827",
        "muted_color": style.get("muted_color") or "#6b7280",
        "font_family": str(style.get("font_family") or "")[:120],
        "foreground_opacity": _clamp_int(style.get("foreground_opacity"), default=92, minimum=0, maximum=100),
        "radius": _clamp_int(style.get("radius"), default=24, minimum=0, maximum=48),
        "width_mode": width_mode,
        "width": _clamp_int(style.get("width"), default=default_width, minimum=520, maximum=1400),
        "columns": _clamp_int(style.get("columns"), default=2, minimum=1, maximum=4),
        "section_gap_mode": section_gap_mode,
        "section_gap": _clamp_int(style.get("section_gap"), default=14, minimum=0, maximum=200),
        "card_gap": _clamp_int(style.get("card_gap"), default=10, minimum=0, maximum=60),
        "section_padding": _clamp_int(style.get("section_padding"), default=15, minimum=0, maximum=80),
        "shadow_strength": _clamp_int(style.get("shadow_strength"), default=1, minimum=0, maximum=5),
        "border_strength": _clamp_int(style.get("border_strength"), default=1, minimum=0, maximum=5),
        "watermark": str(style.get("watermark") or "")[:80],
        "show_updated_at": style.get("show_updated_at", True),
    }


def _css_font_family(value: Any) -> str:
    raw = str(value or "").replace('"', "").strip()
    if not raw:
        return 'Inter, "PingFang SC", "Microsoft YaHei", sans-serif'
    return f'"{raw}", Inter, "PingFang SC", "Microsoft YaHei", sans-serif'


def _card_size(value: Any) -> str:
    size = str(value or "standard").strip().lower()
    return size if size in CARD_SIZE_VALUES else "standard"


def _content_order(item: dict[str, Any]) -> list[str]:
    raw = item.get("content_order")
    values = raw if isinstance(raw, list) else str(raw or "").split(",")
    order: list[str] = []
    for value in values:
        block = str(value).strip()
        if block in CONTENT_BLOCKS and block not in order:
            order.append(block)
    for block in DEFAULT_CONTENT_ORDER:
        if block not in order:
            order.append(block)
    return order[:3]


def _default_item_fonts(size: str) -> dict[str, float]:
    if size == "compact":
        return {"command": 13, "label": 10.5, "description": 10.5}
    if size in {"large", "banner"}:
        return {"command": 16, "label": 12.5, "description": 12.5}
    return {"command": 14, "label": 11.5, "description": 11.5}


def _item_preview_style(item: dict[str, Any]) -> str:
    size = _card_size(item.get("card_size"))
    fonts = _default_item_fonts(size)
    gap = _clamp_int(item.get("content_gap"), default=2, minimum=0, maximum=40)
    command_size = _clamp_float(item.get("command_font_size"), default=fonts["command"], minimum=8, maximum=34)
    label_size = _clamp_float(item.get("label_font_size"), default=fonts["label"], minimum=8, maximum=30)
    description_size = _clamp_float(item.get("description_font_size"), default=fonts["description"], minimum=8, maximum=28)
    return (
        f"--item-content-gap:{gap}px;"
        f"--item-command-size:{command_size:g}px;"
        f"--item-label-size:{label_size:g}px;"
        f"--item-description-size:{description_size:g}px"
    )


def _section_gap_for_menu(menu: dict[str, Any], style: dict[str, Any]) -> int:
    if style.get("section_gap_mode") == "custom":
        return _clamp_int(style.get("section_gap"), default=14, minimum=0, maximum=200)
    sections = menu.get("sections") if isinstance(menu.get("sections"), list) else []
    section_count = max(1, len(sections))
    item_count = sum(len(section.get("items", [])) for section in sections if isinstance(section, dict))
    density = section_count * 1.8 + item_count * 0.35
    return _clamp_int(round(20 - density), default=14, minimum=8, maximum=20)


def _escape(value: Any) -> str:
    return escape(str(value or ""), quote=True).replace("&#x27;", "&#39;")


def _format_time(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return datetime.now().strftime("%Y-%m-%d %H:%M")
    return value.replace("T", " ").replace("+00:00", " UTC")[:19]


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
