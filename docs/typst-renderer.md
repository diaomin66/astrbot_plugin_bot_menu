# Typst render path

## Goal

The plugin has one image render path: Typst. There is no alternate renderer, no remote HTML render fallback, and no local screenshot fallback.

## Fast path

Page saves a `render_snapshot` with a full-card preview raster. When that raster exists, the backend writes the exact saved PNG bytes into the render cache and returns that file. This path avoids second layout, font fallback, text wrapping, color conversion, and resampling, so unchanged saved menus can be served from cache in milliseconds.

## Fallback path

Older menus may not have a full-card raster. For those menus, Typst builds a document from saved geometry, boxes, images, text metrics, text raster layers, and font stacks. This fallback is for compatibility only; to get pixel-identical output, reopen and save the menu in Page so it records a fresh full-card raster.

## Font matching

User fonts live under `plugin_data/astrbot_plugin_bot_menu/fonts/`. Page loads those fonts before saving the raster. Typst also receives the same fonts directory through `font_paths` for older geometry fallback. Cache fingerprints include the selected font file signature so replacing a font invalidates stale images.

## Stability rules

Transparent layers remain transparent. Unsupported visual effects are skipped in geometry fallback instead of becoming visible black boxes. The full-card raster path remains the quality target because it preserves the exact Page preview pixels.

## Usage

No render mode switch is exposed. Save the menu in Page, then use `/menu` or `/menu refresh [menu_id]`; the cache coordinator always uses Typst.
