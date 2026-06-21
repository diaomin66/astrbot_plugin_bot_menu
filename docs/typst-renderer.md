# Typst render path

## Goal

Typst mode is an additional render mode that coexists with the original browser screenshot path. It does not call Chromium, Playwright, or the browser renderer. It reads the Page-saved menu snapshot and compiles a Typst document directly to PNG.

## Data contract with Page

Page saves a `render_snapshot` for Typst. The snapshot includes canvas width/height, capture scale, device pixel ratio, layout metadata, background images, visual boxes, text boxes, relative x/y/width/height normalized back to CSS pixels, colors, background images, box shadow metadata, border radius, border width, opacity, padding, font size, line height, weight, style, letter spacing, alignment, transform metadata, computed font-family stack, and measured text line boxes. Typst uses this snapshot first and falls back to field-based layout only for older menus without a snapshot.

For text, Page records the real rendered line rectangles from the preview DOM. Typst places each saved line at the recorded x/y position when line boxes are present, so wrapping differences between browser layout and Typst do not move later lines.

## Font matching

Typst receives the plugin `fonts/` directory through `font_paths`. When a user selects a custom font, the renderer resolves the actual Typst-visible family from the selected font file and puts that family first in the Typst font stack. The resolved family list is cached during the process so repeated text nodes do not rescan the same font file. This keeps custom-font metrics as close as Typst can make them without using browser layout.

## Stability rules

Transparent Page layers are not emitted as visible Typst rectangles. `rgba(..., 0)`, `transparent`, and unsupported CSS-only backgrounds are skipped unless they also have a visible border. This prevents browser-only CSS effects from degrading into black Typst cards while keeping real Page RGBA fills such as `rgba(241,245,249,.94)` as the same alpha in Typst.

Cached renders are still the latency-critical path for chat usage. If the menu fingerprint is unchanged, the coordinator returns the cached PNG path and does not invoke Typst again.

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
