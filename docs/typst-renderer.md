# Typst render path

## Goal

Typst mode is an additional render mode that coexists with the original browser screenshot path. It does not call Chromium, Playwright, or the browser renderer. It reads the Page-saved menu snapshot and compiles a Typst document directly to PNG.

## Data contract with Page

Page saves a `render_snapshot` for Typst. The snapshot includes canvas width/height, layout metadata, background images, visual boxes, text boxes, relative x/y/width/height, colors, border radius, border width, opacity, font size, line height, weight, alignment, and computed font-family stack. Typst uses this snapshot first and falls back to field-based layout only for older menus without a snapshot.

## Font matching

Typst receives the plugin `fonts/` directory through `font_paths`. When a user selects a custom font, the renderer resolves the actual Typst-visible family from the selected font file and puts that family first in the Typst font stack. This keeps custom-font metrics as close as Typst can make them without using browser layout.

## Limits

This is a true browser-free Typst renderer. The pixel-oriented path depends on Page saving `render_snapshot`; after changing visual rules, reopen and save the menu so Typst receives fresh geometry. Emoji fallback and engine-specific glyph shaping can still differ if Typst and the preview cannot resolve the same font files, so custom fonts should be installed in the plugin `fonts/` directory.

## Usage

Set plugin config:

```json
{
  "render_mode": "typst"
}
```

Then save the menu in Page, or run `/menu refresh [menu_id]` to regenerate the cache.
