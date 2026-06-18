from __future__ import annotations

from datetime import datetime
from typing import Any

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
    style = menu.setdefault("style", {})
    try:
        width = int(style.get("width") or default_width)
    except (TypeError, ValueError):
        width = default_width
    style["width"] = max(520, min(1400, width))
    data = {
        "menu": menu,
        "generated_at": _format_time(menu.get("updated_at")),
    }
    options = {
        "type": "png",
        "full_page": True,
        "omit_background": False,
        "animations": "disabled",
    }
    return MENU_TEMPLATE, data, options


def _format_time(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return datetime.now().strftime("%Y-%m-%d %H:%M")
    return value.replace("T", " ").replace("+00:00", " UTC")[:19]
