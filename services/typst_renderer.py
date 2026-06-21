from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

from .fonts import FontRegistry
from .renderer import (
    _card_size,
    _clamp_float,
    _clamp_int,
    _content_order,
    _normalized_style,
    _section_gap_for_menu,
    preview_width_for_menu,
)

CARD_MIN_HEIGHTS = {
    "compact": 66,
    "standard": 78,
    "large": 112,
    "banner": 118,
}
_FONT_FAMILY_CACHE: dict[str, list[str]] = {}


def render_menu_via_typst(
    menu: dict[str, Any],
    output_dir: str | Path,
    *,
    default_width: int = 900,
    output_scale: int = 4,
    font_registry: FontRegistry | None = None,
) -> str:
    """Render the saved Page menu snapshot through Typst into a PNG file."""

    try:
        import typst
    except ImportError as exc:  # pragma: no cover - exercised only when dependency is missing at runtime
        raise RuntimeError("Typst rendering requires the 'typst' Python package to be installed") from exc

    output_path = _build_output_path(menu, output_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    work_dir = output_path.parent / f".{output_path.stem}-typst"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        source = build_typst_document(
            menu,
            default_width=default_width,
            work_dir=work_dir,
            font_registry=font_registry,
        )
        source_path = work_dir / "menu.typ"
        source_path.write_text(source, encoding="utf-8")
        scale = _clamp_int(output_scale, default=4, minimum=1, maximum=4)
        typst.compile(
            str(source_path),
            str(output_path),
            root=str(work_dir),
            font_paths=_typst_font_paths(font_registry),
            format="png",
            ppi=72 * scale,
        )
        if not output_path.is_file():
            raise RuntimeError("Typst did not create the rendered PNG")
        return str(output_path)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def build_typst_document(
    menu: dict[str, Any],
    *,
    default_width: int = 900,
    work_dir: str | Path | None = None,
    font_registry: FontRegistry | None = None,
) -> str:
    """Build a Typst source document from the exact menu data saved by the Page editor."""

    snapshot = menu.get("render_snapshot") if isinstance(menu.get("render_snapshot"), dict) else None
    if _is_usable_render_snapshot(snapshot):
        return _build_typst_snapshot_document(snapshot, work_dir=Path(work_dir) if work_dir else None, font_registry=font_registry)

    style = _normalized_style(menu, default_width=default_width)
    width = preview_width_for_menu(menu, default_width=default_width)
    section_gap = _section_gap_for_menu(menu, style)
    background_image = _write_background_image(style, Path(work_dir) if work_dir else None)
    foreground_opacity = style["foreground_opacity"] / 100
    columns = style["columns"]
    font_stack = _typst_font_stack(style.get("font_family"), font_registry=font_registry)
    mono_stack = _typst_string_array(["Consolas", "JetBrains Mono", "Microsoft YaHei"])
    sections = ",\n".join(
        _typst_section(section, columns=columns, style=style, width=width)
        for section in menu.get("sections", [])
    )
    footer_right = "" if style["show_updated_at"] is False else "实时预览"
    background_layer = _typst_background_layer(background_image, style, width)
    watermark_layer = ""
    if style["watermark"]:
        watermark_layer = (
            f"#place(bottom + right, dx: -22pt, dy: -16pt, rotate(-8deg, "
            f"text(fill: {_color_expr(style['muted_color'], 0.24)}, size: 38pt, weight: 900, {_typst_str(style['watermark'])})))"
        )

    return f'''// Generated from the Page editor menu snapshot. Do not edit this cache artifact by hand.
#set page(width: {width}pt, height: auto, margin: 0pt, fill: none)
#set text(font: {font_stack}, fill: {_color_expr(style['text_color'])}, size: 12pt, lang: "zh")

#let primary = {_color_expr(style['primary_color'])}
#let muted = {_color_expr(style['muted_color'])}
#let card_fill = {_color_expr(style['card_color'], foreground_opacity)}
#let item_fill = {_color_expr('#f1f5f9', foreground_opacity * 0.94)}
#let border_paint = {_color_expr('#94a3b8', 0.16)}
#let mono_stack = {mono_stack}

#box(width: 100%)[
  #rect(
    width: 100%,
    radius: {style['radius'] or 24}pt,
    fill: {_color_expr(style['background_color'])},
    stroke: (paint: {_color_expr('#94a3b8', 0.18)}, thickness: {max(0, style['border_strength'])}pt),
    inset: 18pt,
  )[
    {background_layer}
    #rect(
      width: 100%,
      radius: {style['radius'] or 24}pt,
      fill: {_color_expr('#ffffff', foreground_opacity)},
      stroke: (paint: {_color_expr('#94a3b8', 0.18)}, thickness: {max(0, style['border_strength'])}pt),
      inset: 16pt,
    )[
      #stack(
        dir: ttb,
        spacing: 0pt,
        text(fill: primary, size: 11pt, weight: 900, tracking: 1.76pt, {_typst_str('Menu ' + str(menu.get('name') or menu.get('id') or ''))}),
        v(12pt),
        text(size: 34pt, weight: 700, {_typst_str(menu.get('title') or 'Bot 功能菜单')}),
        v(4pt),
        text(fill: muted, size: 12pt, {_typst_str(menu.get('subtitle') or '')}),
        v({section_gap}pt),
        stack(dir: ttb, spacing: {section_gap}pt,
{sections}
        ),
        v(16pt),
        grid(columns: (1fr, 1fr), gutter: 12pt,
          text(fill: muted, size: 12pt, {_typst_str(menu.get('footer') or '')}),
          align(right, text(fill: muted, size: 12pt, {_typst_str(footer_right)})),
        ),
      )
    ]
    {watermark_layer}
  ]
]
'''


def _is_usable_render_snapshot(snapshot: dict[str, Any] | None) -> bool:
    if not isinstance(snapshot, dict) or snapshot.get("renderer") != "typst-direct":
        return False
    try:
        return float(snapshot.get("width") or 0) > 0 and float(snapshot.get("height") or 0) > 0
    except (TypeError, ValueError):
        return False


def _build_typst_snapshot_document(
    snapshot: dict[str, Any],
    *,
    work_dir: Path | None,
    font_registry: FontRegistry | None,
) -> str:
    width = _clamp_float(snapshot.get("width"), default=900, minimum=1, maximum=4000)
    height = _clamp_float(snapshot.get("height"), default=1200, minimum=1, maximum=8000)
    images = [_snapshot_image(element, work_dir) for element in snapshot.get("images", []) if isinstance(element, dict)]
    boxes = [element for element in snapshot.get("boxes", []) if isinstance(element, dict)]
    texts = [element for element in snapshot.get("texts", []) if isinstance(element, dict)]
    card_boxes = [element for element in boxes if element.get("role") == "card"]
    other_boxes = [element for element in boxes if element.get("role") != "card"]
    elements = []
    elements.extend(_snapshot_box(element) for element in card_boxes)
    elements.extend(element for element in images if element)
    elements.extend(_snapshot_box(element) for element in other_boxes)
    elements.extend(_snapshot_text(element, font_registry=font_registry) for element in texts)
    body = "\n".join(element for element in elements if element)
    return f'''// Generated from Page render_snapshot. Typst renders directly from saved geometry; no browser is used here.
#set page(width: {width:g}pt, height: {height:g}pt, margin: 0pt, fill: none)
#set text(lang: "zh")
{body}
'''


def _snapshot_box(element: dict[str, Any]) -> str:
    rect = _snapshot_rect(element)
    if not rect:
        return ""
    x, y, width, height = rect
    fill_color, fill_alpha = _css_color_components(
        element.get("background"),
        opacity=element.get("opacity", 1),
        fallback_alpha=0,
    )
    stroke_width = _clamp_float(element.get("border_width"), default=0, minimum=0, maximum=20)
    stroke_color, stroke_alpha = _css_color_components(element.get("border_color"), fallback_alpha=0)
    if fill_alpha <= 0 and (stroke_width <= 0 or stroke_alpha <= 0):
        return ""
    fill = f", fill: {_color_expr(fill_color, fill_alpha)}" if fill_alpha > 0 else ""
    stroke = ""
    if stroke_width > 0 and stroke_alpha > 0:
        stroke = f", stroke: (paint: {_color_expr(stroke_color, stroke_alpha)}, thickness: {stroke_width:g}pt)"
    radius = _clamp_float(element.get("border_radius"), default=0, minimum=0, maximum=200)
    return f"#place(top + left, dx: {x:g}pt, dy: {y:g}pt, rect(width: {width:g}pt, height: {height:g}pt, radius: {radius:g}pt{fill}{stroke}))"


def _snapshot_image(element: dict[str, Any], work_dir: Path | None) -> str:
    rect = _snapshot_rect(element)
    if not rect:
        return ""
    image_path = _write_data_url_image(str(element.get("src") or ""), work_dir)
    if not image_path:
        return ""
    x, y, width, height = rect
    return f"#place(top + left, dx: {x:g}pt, dy: {y:g}pt, image({_typst_str(image_path)}, width: {width:g}pt, height: {height:g}pt))"


def _snapshot_text(element: dict[str, Any], *, font_registry: FontRegistry | None) -> str:
    rect = _snapshot_rect(element)
    text = str(element.get("text") or "")
    if not rect or text == "":
        return ""
    x, y, width, height = rect
    padding = _snapshot_sides(element.get("padding"))
    if padding:
        top, right, bottom, left = padding
        x += left
        y += top
        width = max(1, width - left - right)
        height = max(1, height - top - bottom)
    font_size = _clamp_float(element.get("font_size"), default=12, minimum=1, maximum=200)
    line_height = _clamp_float(element.get("line_height"), default=font_size * 1.2, minimum=1, maximum=300)
    color, alpha = _css_color_components(element.get("color"), opacity=element.get("opacity", 1))
    if alpha <= 0:
        return ""
    fill = _color_expr(color, alpha)
    weight = _typst_weight(element.get("font_weight"))
    families = element.get("font_family") if isinstance(element.get("font_family"), list) else []
    font_stack = _typst_snapshot_font_stack(families, font_registry=font_registry)
    align = "right" if str(element.get("text_align") or "").lower() == "right" else "left"
    tracking = _clamp_float(element.get("letter_spacing"), default=0, minimum=-20, maximum=80)
    leading = max(0.0, line_height - font_size)
    style = str(element.get("font_style") or "").strip().lower()
    style_arg = f", style: {_typst_str(style)}" if style in {"italic", "oblique"} else ""
    glyph_elements = _snapshot_text_glyphs(
        element.get("glyphs"),
        font_stack=font_stack,
        font_size=font_size,
        fill=fill,
        weight=weight,
        style_arg=style_arg,
    )
    if glyph_elements:
        return "\n".join(glyph_elements)
    line_elements = _snapshot_text_lines(
        element.get("lines"),
        font_stack=font_stack,
        font_size=font_size,
        fill=fill,
        weight=weight,
        tracking=tracking,
        style_arg=style_arg,
    )
    if line_elements:
        return "\n".join(line_elements)
    content = (
        f"set text(font: {font_stack}, size: {font_size:g}pt, fill: {fill}, weight: {weight}, "
        f"tracking: {tracking:g}pt, top-edge: \"bounds\", bottom-edge: \"bounds\"{style_arg});"
        f"set par(leading: {leading:g}pt, justify: false);"
        f"show text: set block(above: 0pt, below: 0pt);"
        f"align({align}, text({_typst_str(text)}))"
    )
    return (
        f"#place(top + left, dx: {x:g}pt, dy: {y:g}pt, "
        f"box(width: {max(width, 4000) if align == 'left' else width:g}pt, height: {height:g}pt)[#{{{content}}}])"
    )


def _snapshot_text_glyphs(
    value: Any,
    *,
    font_stack: str,
    font_size: float,
    fill: str,
    weight: int | str,
    style_arg: str,
) -> list[str]:
    if not isinstance(value, list):
        return []
    rendered: list[str] = []
    for glyph in value:
        if not isinstance(glyph, dict):
            continue
        text = str(glyph.get("text") or "")
        rect = _snapshot_rect(glyph)
        if not text or not rect:
            continue
        x, y, width, height = rect
        content = (
            f"set text(font: {font_stack}, size: {font_size:g}pt, fill: {fill}, weight: {weight}, "
            f"tracking: 0pt, top-edge: \"bounds\", bottom-edge: \"bounds\"{style_arg});"
            f"show text: set block(above: 0pt, below: 0pt);"
            f"text({_typst_str(text)})"
        )
        rendered.append(
            f"#place(top + left, dx: {x:g}pt, dy: {y:g}pt, "
            f"box(width: {max(1, width + 2):g}pt, height: {height:g}pt)[#{{{content}}}])"
        )
    return rendered


def _snapshot_text_lines(
    value: Any,
    *,
    font_stack: str,
    font_size: float,
    fill: str,
    weight: int | str,
    tracking: float,
    style_arg: str,
) -> list[str]:
    if not isinstance(value, list):
        return []
    rendered: list[str] = []
    for line in value:
        if not isinstance(line, dict):
            continue
        text = str(line.get("text") or "")
        rect = _snapshot_rect(line)
        if not text or not rect:
            continue
        x, y, width, height = rect
        content = (
            f"set text(font: {font_stack}, size: {font_size:g}pt, fill: {fill}, weight: {weight}, "
            f"tracking: {tracking:g}pt, top-edge: \"bounds\", bottom-edge: \"bounds\"{style_arg});"
            f"set par(leading: 0pt, justify: false);"
            f"show text: set block(above: 0pt, below: 0pt);"
            f"text({_typst_str(text)})"
        )
        rendered.append(
            f"#place(top + left, dx: {x:g}pt, dy: {y:g}pt, "
            f"box(width: {max(width + 2, 4000):g}pt, height: {height:g}pt)[#{{{content}}}])"
        )
    return rendered


def _typst_section(section: dict[str, Any], *, columns: int, style: dict[str, Any], width: int) -> str:
    section_padding = style["section_padding"]
    card_gap = style["card_gap"]
    item_area_width = max(1, width - 18 * 2 - 16 * 2 - section_padding * 2)
    column_width = max(1, (item_area_width - card_gap * max(0, columns - 1)) / max(1, columns))
    column_spec = _typst_columns(columns)
    cells: list[str] = []
    for item in section.get("items", []):
        size = _card_size(item.get("card_size"))
        item_width = item_area_width if size == "banner" else column_width
        item_block = _typst_item(item, style=style, width=item_width)
        if size == "banner" and columns > 1:
            cells.append(f"grid.cell(colspan: {columns})[#{item_block}]")
        else:
            cells.append(item_block)
    cell_source = ",\n              ".join(cells)
    return f'''          rect(
            width: 100%,
            radius: 18pt,
            fill: card_fill,
            stroke: (paint: border_paint, thickness: {max(0, style['border_strength'])}pt),
            inset: {section_padding}pt,
          )[
            #stack(
              dir: ttb,
              spacing: 10pt,
              text(size: 13pt, weight: 700, {_typst_str(section.get('title') or '分组')}),
              grid(columns: {column_spec}, gutter: {card_gap}pt,
              {cell_source}
              ),
            )
          ]'''


def _typst_item(item: dict[str, Any], *, style: dict[str, Any], width: float) -> str:
    size = _card_size(item.get("card_size"))
    disabled = item.get("enabled") is False
    height = _estimated_item_height(item, width)
    icon_col = {"compact": 28, "standard": 34, "large": 42, "banner": 46}[size]
    gap = {"compact": 8, "standard": 10, "large": 10, "banner": 10}[size]
    inset = {"compact": 8, "standard": 11, "large": 14, "banner": 16}[size]
    icon_size = {"compact": 18, "standard": 22, "large": 26, "banner": 26}[size]
    fill_opacity = 0.45 if disabled else style["foreground_opacity"] / 100 * 0.94
    text_opacity = 0.45 if disabled else 1
    content_blocks = ",\n                  ".join(_typst_item_block(item, block, disabled=disabled, style=style) for block in _content_order(item))
    return f'''rect(
                width: 100%,
                height: {height:g}pt,
                radius: 13pt,
                fill: {_color_expr('#f1f5f9', fill_opacity)},
                stroke: (paint: {_color_expr('#94a3b8', 0.16)}, thickness: {max(0, style['border_strength'])}pt),
                inset: {inset}pt,
              )[
                #grid(columns: ({icon_col}pt, 1fr), gutter: {gap}pt,
                  align(center + top, text(fill: {_color_expr(style['primary_color'], text_opacity)}, size: {icon_size}pt, {_typst_str(item.get('icon') or '•')})),
                  stack(dir: ttb, spacing: {_clamp_int(item.get('content_gap'), default=2, minimum=0, maximum=40)}pt,
                  {content_blocks}
                  ),
                )
              ]'''


def _typst_item_block(item: dict[str, Any], block: str, *, disabled: bool, style: dict[str, Any]) -> str:
    size = _card_size(item.get("card_size"))
    defaults = _default_item_fonts(size)
    opacity = 0.45 if disabled else 1
    if block == "command":
        font_size = _clamp_float(item.get("command_font_size"), default=defaults["command"], minimum=8, maximum=34)
        return (
            f'text(font: mono_stack, fill: {_color_expr(style["primary_color"], opacity)}, '
            f'size: {font_size:g}pt, weight: 800, {_typst_str(item.get("command") or "")})'
        )
    if block == "label":
        font_size = _clamp_float(item.get("label_font_size"), default=defaults["label"], minimum=8, maximum=30)
        return f'text(fill: {_color_expr(style["text_color"], opacity)}, size: {font_size:g}pt, weight: 650, {_typst_str(item.get("label") or "未命名")})'
    font_size = _clamp_float(item.get("description_font_size"), default=defaults["description"], minimum=8, maximum=28)
    return f'text(fill: {_color_expr(style["muted_color"], opacity)}, size: {font_size:g}pt, {_typst_str(item.get("description") or "")})'


def _typst_background_layer(background_image: str, style: dict[str, Any], width: int) -> str:
    layers: list[str] = []
    if background_image:
        image_width = max(1, width * style["background_image_width"] / 100)
        dx = width * style["background_image_x"] / 100
        dy = width * style["background_image_y"] / 100
        layers.append(
            f"#place(top + left, dx: {dx:g}pt, dy: {dy:g}pt, image({_typst_str(background_image)}, width: {image_width:g}pt))"
        )
    overlay = style["background_overlay"] / 100
    if overlay > 0:
        layers.append(f"#place(top + left, rect(width: 100%, height: 100%, fill: {_color_expr('#0f172a', overlay)}))")
    return "\n    ".join(layers)


def _write_background_image(style: dict[str, Any], work_dir: Path | None) -> str:
    source = str(style.get("background_image") or "")
    if not source.startswith("data:image/") or work_dir is None:
        return ""
    try:
        header, payload = source.split(",", 1)
        if ";base64" not in header:
            return ""
        mime = header.split(";", 1)[0].split(":", 1)[1]
        suffix = ".jpg" if mime in {"image/jpeg", "image/jpg"} else ".png"
        digest = hashlib.sha1(payload.encode("ascii", errors="ignore")).hexdigest()[:12]
        path = work_dir / f"background-{digest}{suffix}"
        path.write_bytes(base64.b64decode(payload))
        return path.name
    except Exception:
        return ""


def _write_data_url_image(source: str, work_dir: Path | None) -> str:
    if not source.startswith("data:image/") or work_dir is None:
        return ""
    try:
        header, payload = source.split(",", 1)
        if ";base64" not in header:
            return ""
        mime = header.split(";", 1)[0].split(":", 1)[1]
        suffix = ".jpg" if mime in {"image/jpeg", "image/jpg"} else ".png"
        digest = hashlib.sha1(payload.encode("ascii", errors="ignore")).hexdigest()[:12]
        path = work_dir / f"snapshot-image-{digest}{suffix}"
        path.write_bytes(base64.b64decode(payload))
        return path.name
    except Exception:
        return ""


def _snapshot_rect(element: dict[str, Any]) -> tuple[float, float, float, float] | None:
    rect = element.get("rect") if isinstance(element.get("rect"), dict) else {}
    try:
        x = float(rect.get("x") or 0)
        y = float(rect.get("y") or 0)
        width = float(rect.get("width") or 0)
        height = float(rect.get("height") or 0)
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return (round(x, 3), round(y, 3), round(width, 3), round(height, 3))


def _snapshot_sides(value: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(value, dict):
        return None
    try:
        top = _clamp_float(value.get("top"), default=0, minimum=0, maximum=400)
        right = _clamp_float(value.get("right"), default=0, minimum=0, maximum=400)
        bottom = _clamp_float(value.get("bottom"), default=0, minimum=0, maximum=400)
        left = _clamp_float(value.get("left"), default=0, minimum=0, maximum=400)
    except (TypeError, ValueError):
        return None
    return (top, right, bottom, left)


def _estimated_item_height(item: dict[str, Any], width: float) -> float:
    size = _card_size(item.get("card_size"))
    defaults = _default_item_fonts(size)
    min_height = CARD_MIN_HEIGHTS[size]
    icon_col = {"compact": 28, "standard": 34, "large": 42, "banner": 46}[size]
    gap = {"compact": 8, "standard": 10, "large": 10, "banner": 10}[size]
    inset = {"compact": 8, "standard": 11, "large": 14, "banner": 16}[size]
    text_width = max(24, width - icon_col - gap - inset * 2)
    block_sizes = {
        "command": _clamp_float(item.get("command_font_size"), default=defaults["command"], minimum=8, maximum=34),
        "label": _clamp_float(item.get("label_font_size"), default=defaults["label"], minimum=8, maximum=30),
        "description": _clamp_float(item.get("description_font_size"), default=defaults["description"], minimum=8, maximum=28),
    }
    block_text = {
        "command": str(item.get("command") or ""),
        "label": str(item.get("label") or "未命名"),
        "description": str(item.get("description") or ""),
    }
    line_height = {"command": 1.18, "label": 1.28, "description": 1.34}
    visible = 0
    content_height = 0.0
    for block in _content_order(item):
        text = block_text[block]
        if not text:
            continue
        font_size = block_sizes[block]
        chars_per_line = max(1, int(text_width / max(4.5, font_size * 0.62)))
        lines = max(1, (len(text) + chars_per_line - 1) // chars_per_line)
        if visible:
            content_height += _clamp_int(item.get("content_gap"), default=2, minimum=0, maximum=40)
        content_height += lines * font_size * line_height[block]
        visible += 1
    return max(float(min_height), inset * 2 + content_height)


def _default_item_fonts(size: str) -> dict[str, float]:
    if size == "compact":
        return {"command": 13, "label": 10.5, "description": 10.5}
    if size in {"large", "banner"}:
        return {"command": 16, "label": 12.5, "description": 12.5}
    return {"command": 14, "label": 11.5, "description": 11.5}


def _typst_font_paths(font_registry: FontRegistry | None) -> list[str]:
    if not font_registry:
        return []
    return [str(font_registry.fonts_dir)] if font_registry.fonts_dir.is_dir() else []


def _typst_font_stack(value: Any, *, font_registry: FontRegistry | None = None) -> str:
    values: list[str] = []
    font = font_registry.resolve(value) if font_registry else None
    if font:
        values.extend(_typst_font_families_for_file(font.path))
        values.extend([font.name, font.family])
    raw = str(value or "").strip().strip("\"'")
    if raw:
        values.append(raw)
    values.extend(["Inter", "Microsoft YaHei", "Noto Sans CJK SC", "Arial"])
    deduped: list[str] = []
    for item in values:
        if item and item not in deduped:
            deduped.append(item)
    return _typst_string_array(deduped)


def _typst_snapshot_font_stack(values: list[Any], *, font_registry: FontRegistry | None = None) -> str:
    families: list[str] = []
    for value in values:
        raw = str(value or "").strip().strip("\"'")
        if not raw:
            continue
        font = font_registry.resolve(raw) if font_registry else None
        if font:
            families.extend(_typst_font_families_for_file(font.path))
            families.extend([font.name, font.family])
        families.append(raw)
    families.extend(["Inter", "Microsoft YaHei", "Noto Sans CJK SC", "Arial"])
    deduped: list[str] = []
    for family in families:
        if family and family not in deduped:
            deduped.append(family)
    return _typst_string_array(deduped)


def _typst_font_families_for_file(path: Path) -> list[str]:
    key = str(path.resolve())
    cached = _FONT_FAMILY_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        import typst
    except ImportError:
        return []
    try:
        target = path.resolve()
        fonts = typst.Fonts(font_paths=[str(target.parent)])
        families = [
            font.family
            for font in fonts.fonts()
            if getattr(font, "path", "") and Path(str(font.path)).resolve() == target
        ]
        _FONT_FAMILY_CACHE[key] = families
        return families
    except Exception:
        _FONT_FAMILY_CACHE[key] = []
        return []


def _typst_columns(columns: int) -> str:
    return "(" + ", ".join("1fr" for _ in range(max(1, columns))) + ")"


def _typst_string_array(values: list[str]) -> str:
    return "(" + ", ".join(_typst_str(value) for value in values) + ")"


def _typst_str(value: Any) -> str:
    return json.dumps(str(value or ""), ensure_ascii=False)


def _color_expr(value: str, opacity: float = 1.0) -> str:
    raw = str(value or "#000000").strip()
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", raw):
        raw = "#000000"
    opacity = max(0.0, min(1.0, float(opacity)))
    transparent = round((1 - opacity) * 100, 3)
    if transparent <= 0:
        return f"rgb(\"{raw}\")"
    return f"rgb(\"{raw}\").transparentize({transparent:g}%)"


def _css_color_expr(value: Any, opacity: Any = 1.0) -> str:
    color, alpha = _css_color_components(value, opacity=opacity)
    return _color_expr(color, alpha)


def _css_color_components(
    value: Any,
    opacity: Any = 1.0,
    *,
    fallback: str = "#000000",
    fallback_alpha: float = 1.0,
) -> tuple[str, float]:
    raw = str(value or "").strip()
    try:
        opacity_value = max(0.0, min(1.0, float(opacity)))
    except (TypeError, ValueError):
        opacity_value = 1.0
    if not raw or raw.lower() == "transparent":
        return (fallback, 0.0)
    if raw.startswith("#"):
        color = raw
        if re.fullmatch(r"#[0-9A-Fa-f]{3}", color):
            color = "#" + "".join(ch * 2 for ch in color[1:])
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
            return (fallback, max(0.0, min(1.0, fallback_alpha)) * opacity_value)
        return (color, opacity_value)
    match = re.fullmatch(r"rgba?\(([^)]+)\)", raw.replace(" ", ""))
    if not match:
        return (fallback, max(0.0, min(1.0, fallback_alpha)) * opacity_value)
    parts = match.group(1).split(",")
    if len(parts) < 3:
        return (fallback, max(0.0, min(1.0, fallback_alpha)) * opacity_value)
    try:
        r, g, b = [max(0, min(255, int(float(part)))) for part in parts[:3]]
        alpha = float(parts[3]) if len(parts) >= 4 else 1.0
    except ValueError:
        return (fallback, max(0.0, min(1.0, fallback_alpha)) * opacity_value)
    return (f"#{r:02x}{g:02x}{b:02x}", opacity_value * max(0.0, min(1.0, alpha)))


def _typst_weight(value: Any) -> int | str:
    raw = str(value or "400").strip().lower()
    if raw == "bold":
        return 700
    if raw == "normal":
        return 400
    try:
        return max(100, min(900, int(float(raw))))
    except ValueError:
        return 400


def _build_output_path(menu: dict[str, Any], output_dir: str | Path) -> Path:
    raw = json.dumps(menu, ensure_ascii=False, sort_keys=True).encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()[:12]
    safe_id = "".join(ch for ch in str(menu.get("id") or "menu") if ch.isalnum() or ch in ("_", "-")) or "menu"
    return Path(output_dir) / "rendered" / f"{safe_id}-typst-{digest}.png"

