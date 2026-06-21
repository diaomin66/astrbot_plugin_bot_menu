# Typst render path

## Goal

Typst mode is an additional render mode that coexists with the original browser screenshot path. It does not call Chromium, Playwright, or the browser renderer. It reads the Page-saved menu snapshot and compiles a Typst document directly to PNG.

## Data contract with Page

Page saves a `render_snapshot` for Typst. The snapshot includes canvas width/height, capture scale, device pixel ratio, a full-card preview raster layer, layout metadata, background images, visual boxes, text boxes, relative x/y/width/height normalized back to CSS pixels, colors, background images, box shadow metadata, border radius, border width, opacity, padding, font size, line height, weight, style, letter spacing, alignment, `text-transform`, transform metadata, computed font-family stack, measured text line boxes, measured grapheme boxes, and transparent text raster fallback layers. Typst uses this snapshot first and falls back to field-based layout only for older menus without a snapshot.

When the full-card preview raster is available, Typst embeds that saved PNG as the final page and skips the structured boxes/text fallback. This is the highest-fidelity path for shadows, gradients, filters, text shaping, anti-aliasing, and exact Page preview placement while keeping Typst browser-free at render time.

For text fallback, Page records the final visible text after CSS `text-transform`, the real rendered line rectangles, grapheme rectangles, and a transparent PNG layer drawn at Page-save time. Typst embeds that saved raster text layer first, so browser font shaping, case conversion, emoji fallback, and wrapping are already fixed before Typst runs. If a raster layer is unavailable, Typst falls back to saved grapheme boxes, then saved line boxes, then to a whole text box. Line and whole-text fallback boxes are deliberately widened so Typst does not introduce new line breaks that were not present in Page.

## Font matching

Typst receives the plugin `fonts/` directory through `font_paths`. When a user selects a custom font, the renderer resolves the actual Typst-visible family from the selected font file and puts that family first in the Typst font stack. The resolved family list is cached during the process so repeated text nodes do not rescan the same font file. This keeps custom-font metrics as close as Typst can make them without using browser layout.

For the highest-fidelity full-card raster path, Page waits for `document.fonts.ready` before measuring text or saving the snapshot, then embeds the same `#botMenuUserFonts` `@font-face` CSS inside the SVG `foreignObject` used for the saved raster. The raster-only CSS changes `font-display: swap` to `font-display: block` so the one-shot capture does not paint a fallback font before the selected font is available.

## Stability rules

Transparent Page layers are not emitted as visible Typst rectangles. `rgba(..., 0)`, `transparent`, and unsupported CSS-only backgrounds are skipped unless they also have a visible border. This prevents browser-only CSS effects from degrading into black Typst cards while keeping real Page RGBA fills such as `rgba(241,245,249,.94)` as the same alpha in Typst.

Cached renders are still the latency-critical path for chat usage. If the menu fingerprint is unchanged, the coordinator returns the cached PNG path and does not invoke Typst again.

When Page saves a menu in `typst` mode and the full-card raster is present, the plugin materializes that saved raster directly into the Typst render cache. This makes the cache ready immediately after save without waiting for a background Typst compile; if the saved raster is missing or invalid, the normal Typst compile fallback is still scheduled.

The full-card raster path has a pixel-diff regression test: a saved RGBA PNG is embedded through Typst at the same CSS-pixel size, rendered back to PNG, and compared pixel-for-pixel with the saved raster. This locks the highest-fidelity path against Typst-side reflow, color conversion, or black fallback layers.

## Limits

This is a true browser-free Typst renderer. The pixel-oriented path depends on Page saving `render_snapshot`; after changing visual rules or font files, reopen and save the menu so Typst receives fresh geometry and the refreshed saved raster. Emoji fallback and engine-specific glyph shaping can still differ if Typst and the preview cannot resolve the same font files, so custom fonts should be installed in the plugin `fonts/` directory.

## Usage

Set plugin config:

```json
{
  "render_mode": "typst"
}
```

Then save the menu in Page, or run `/menu refresh [menu_id]` to regenerate the cache.
