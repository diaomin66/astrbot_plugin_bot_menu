## 2026-06-20 - Task: Fix Page style changes not applying after save
### What was done
- Fixed the Page save flow so live modal controls are flushed before the save payload is built, preventing recently edited layout/style values from being lost in older WebView or quick Ctrl+S save paths.
- Added regression coverage to lock the ordering: flush modal controls first, then sync the menu model, then POST `menus/save`.
- Synced the updated Page runtime file to the local AstrBot instance plugin directory.

### Testing
- `python -m unittest discover -s tests -v` -> 45 tests passed.
- `python -m compileall -q .` -> passed.
- Browser smoke test via localhost harness: Page loaded, style modal changed preview metadata to `每行 4 张`, Ctrl+S reported save success.
- Local AstrBot sync verification: `pages/menu-editor/app.js` SHA256 matched between repository and `C:\Users\21340\.astrbot_launcher\instances\263ca536-4cb7-4f22-b872-e68958ec3dc8\core\data\plugins\astrbot_plugin_bot_menu\pages\menu-editor\app.js`.

### Notes
- `pages/menu-editor/app.js`：保存前强制派发当前弹窗控件的 input/change，并兼容旧 WebView 的 `document.createEvent` 路径。
- `tests/test_menu_services.py`：新增 Page 保存顺序回归测试，防止未来再次先构建旧 payload 再保存。
- 回滚方式：`git checkout -- pages/menu-editor/app.js tests/test_menu_services.py progress.md`，并将目标 AstrBot 插件目录中的 `pages/menu-editor/app.js` 恢复为 PR 前版本或重新从上一提交复制。
