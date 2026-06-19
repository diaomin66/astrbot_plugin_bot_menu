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

MENU_TEMPLATE = r"""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <style>
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; }
    body {
      width: {{ menu.style.width }}px;
      padding: 28px;
      font-family: "Inter", "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
      color: {{ menu.style.text_color }};
      background:
        radial-gradient(circle at top left, {{ menu.style.primary_color }}33, transparent 34%),
        linear-gradient(135deg, {{ menu.style.background_color }}, #ffffff 72%);
    }
    .shell {
      border-radius: {{ menu.style.radius }}px;
      padding: 30px;
      background: rgba(255, 255, 255, 0.78);
      border: 1px solid rgba(255, 255, 255, 0.7);
      box-shadow: 0 24px 70px rgba(15, 23, 42, 0.14);
      overflow: hidden;
      position: relative;
    }
    .shell::before {
      content: "";
      position: absolute;
      inset: 0 0 auto 0;
      height: 8px;
      background: linear-gradient(90deg, {{ menu.style.primary_color }}, #06b6d4, #22c55e);
    }
    header { position: relative; padding: 12px 0 24px; }
    .eyebrow {
      display: inline-flex;
      gap: 8px;
      align-items: center;
      padding: 7px 12px;
      border-radius: 999px;
      color: {{ menu.style.primary_color }};
      background: {{ menu.style.primary_color }}14;
      font-size: 18px;
      font-weight: 700;
    }
    h1 {
      margin: 16px 0 8px;
      font-size: 46px;
      line-height: 1.08;
      letter-spacing: -0.04em;
    }
    .subtitle { color: {{ menu.style.muted_color }}; font-size: 22px; line-height: 1.55; }
    .sections { display: grid; gap: 18px; }
    .section {
      padding: 22px;
      border-radius: {{ menu.style.radius }}px;
      background: {{ menu.style.card_color }};
      border: 1px solid rgba(148, 163, 184, 0.22);
      box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
    }
    .section-title {
      margin: 0 0 16px;
      font-size: 24px;
      font-weight: 800;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .section-title::before {
      content: "";
      width: 10px;
      height: 24px;
      border-radius: 999px;
      background: {{ menu.style.primary_color }};
      display: inline-block;
    }
    .items { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .item {
      display: grid;
      grid-template-columns: 44px 1fr;
      gap: 12px;
      min-height: 88px;
      padding: 15px;
      border-radius: max(14px, calc({{ menu.style.radius }}px - 8px));
      background: linear-gradient(180deg, rgba(248, 250, 252, 0.92), rgba(241, 245, 249, 0.72));
      border: 1px solid rgba(148, 163, 184, 0.18);
      opacity: 1;
    }
    .item.disabled { opacity: 0.46; filter: grayscale(0.4); }
    .icon {
      width: 44px;
      height: 44px;
      display: grid;
      place-items: center;
      border-radius: 14px;
      font-size: 25px;
      background: {{ menu.style.primary_color }}18;
    }
    .label-row { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
    .label { font-size: 21px; font-weight: 800; }
    .command {
      font-size: 17px;
      font-family: "Cascadia Mono", "Consolas", monospace;
      color: {{ menu.style.primary_color }};
      background: {{ menu.style.primary_color }}10;
      padding: 3px 8px;
      border-radius: 8px;
      word-break: break-all;
    }
    .desc { margin-top: 7px; color: {{ menu.style.muted_color }}; font-size: 17px; line-height: 1.45; }
    footer {
      display: flex;
      justify-content: space-between;
      gap: 18px;
      margin-top: 22px;
      color: {{ menu.style.muted_color }};
      font-size: 16px;
    }
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div class="eyebrow">📋 {{ menu.name | e }}</div>
      <h1>{{ menu.title | e }}</h1>
      {% if menu.subtitle %}<div class="subtitle">{{ menu.subtitle | e }}</div>{% endif %}
    </header>

    <div class="sections">
      {% for section in menu.sections %}
      <section class="section">
        <h2 class="section-title">{{ section.title | e }}</h2>
        <div class="items">
          {% for item in section.items %}
          <article class="item {% if not item.enabled %}disabled{% endif %}">
            <div class="icon">{{ item.icon or "•" }}</div>
            <div>
              <div class="label-row">
                <span class="label">{{ item.label | e }}</span>
                {% if item.command %}<span class="command">{{ item.command | e }}</span>{% endif %}
              </div>
              {% if item.description %}<div class="desc">{{ item.description | e }}</div>{% endif %}
            </div>
          </article>
          {% endfor %}
        </div>
      </section>
      {% endfor %}
    </div>

    <footer>
      <span>{{ menu.footer | e }}</span>
      {% if menu.style.show_updated_at %}<span>更新：{{ generated_at }}</span>{% endif %}
    </footer>
  </main>
</body>
</html>
"""


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
        f"--preview-width:{width}px;"
        f"--preview-columns:{style['columns']};"
        f"--preview-section-gap:{section_gap}px;"
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
      background: radial-gradient(circle at top left, color-mix(in srgb, var(--preview-primary, #7c3aed), transparent 70%), transparent 35%), var(--preview-bg, #f8fafc);
      text-rendering: geometricPrecision;
      -webkit-font-smoothing: antialiased;
      position: relative;
      overflow: hidden;
    }}
    .preview-bg-image {{
      position: absolute;
      z-index: 0;
      max-width: none;
      height: auto;
      user-select: none;
      pointer-events: none;
    }}
    .preview-card .kicker {{ color: var(--preview-primary, #7c3aed); }}
    .preview-inner {{ position: relative; z-index: 1; padding: 22px; border-radius: inherit; background: rgba(255,255,255,var(--preview-foreground-opacity, .92)); box-shadow: 0 16px 34px rgba(15,23,42,.10); }}
    .preview-title {{ margin: 12px 0 4px; font-size: 34px; line-height: 1.1; }}
    .preview-sections {{ display: grid; gap: var(--preview-section-gap, 14px); margin-top: var(--preview-section-gap, 14px); }}
    .preview-section {{ padding: 15px; border-radius: 18px; background: color-mix(in srgb, var(--preview-card, #fff) calc(var(--preview-foreground-opacity, .92) * 100%), transparent); }}
    .preview-items {{ display: grid; grid-template-columns: repeat(var(--preview-columns, 2), minmax(0, 1fr)); gap: 10px; }}
    .preview-item {{ display: grid; grid-template-columns: 34px 1fr; gap: 9px; min-height: 72px; padding: 10px; border-radius: 13px; background: rgba(241,245,249,var(--preview-foreground-opacity, .94)); }}
    .preview-item.size-compact {{ grid-template-columns: 28px 1fr; min-height: 58px; padding: 8px; }}
    .preview-item.size-large {{ grid-template-columns: 42px 1fr; min-height: 104px; padding: 14px; }}
    .preview-item.size-banner {{ grid-column: 1 / -1; grid-template-columns: 46px 1fr; min-height: 112px; padding: 16px; }}
    .preview-item.disabled {{ opacity: .45; }}
    .preview-command {{ color: var(--preview-primary, #7c3aed); font-family: Consolas, monospace; font-size: 12px; }}
    .preview-desc, .preview-sub, .preview-footer {{ color: var(--preview-muted, #6b7280); }}
    .preview-footer {{ display: flex; justify-content: space-between; margin-top: 16px; font-size: 12px; }}
  </style>
</head>
<body>
  <div class="preview-card" style="{style_attr}">
    {background_markup}
    <div class="preview-inner">
      <div class="kicker">📋 {_escape(menu.get("name") or menu.get("id"))}</div>
      <h1 class="preview-title">{_escape(menu.get("title") or "Bot 功能菜单")}</h1>
      <div class="preview-sub">{_escape(menu.get("subtitle") or "")}</div>
      <div class="preview-sections">
      {sections}
      </div>
      <div class="preview-footer"><span>{_escape(menu.get("footer") or "")}</span><span>{footer_status}</span></div>
    </div>
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
    return f"""<div class="preview-item size-{size}{disabled}">
            <div>{_escape(item.get("icon") or "•")}</div>
            <div><strong>{_escape(item.get("label") or "未命名")}</strong><div class="preview-command">{_escape(item.get("command") or "")}</div><div class="preview-desc">{_escape(item.get("description") or "")}</div></div>
          </div>"""


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
        "card_color": style.get("card_color") or "#ffffff",
        "text_color": style.get("text_color") or "#111827",
        "muted_color": style.get("muted_color") or "#6b7280",
        "foreground_opacity": _clamp_int(style.get("foreground_opacity"), default=92, minimum=0, maximum=100),
        "radius": _clamp_int(style.get("radius"), default=24, minimum=0, maximum=48),
        "width_mode": width_mode,
        "width": _clamp_int(style.get("width"), default=default_width, minimum=520, maximum=1400),
        "columns": _clamp_int(style.get("columns"), default=2, minimum=1, maximum=4),
        "section_gap_mode": section_gap_mode,
        "section_gap": _clamp_int(style.get("section_gap"), default=14, minimum=4, maximum=40),
        "show_updated_at": style.get("show_updated_at", True),
    }


def _card_size(value: Any) -> str:
    size = str(value or "standard").strip().lower()
    return size if size in CARD_SIZE_VALUES else "standard"


def _section_gap_for_menu(menu: dict[str, Any], style: dict[str, Any]) -> int:
    if style.get("section_gap_mode") == "custom":
        return _clamp_int(style.get("section_gap"), default=14, minimum=4, maximum=40)
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
