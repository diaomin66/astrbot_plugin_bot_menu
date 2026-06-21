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

## 2026-06-20 - Task: Deeply verify and repair Page editor buttons and save/render flow
### What was done
- Replaced remaining Page flows that depended on native `confirm` / `prompt` with in-page modal dialogs so WebView-hosted buttons work consistently for delete, reset, style copy, dirty-leave, and draft recovery flows.
- Wrapped modal and entity-row action buttons with the shared async-safe action runner so failed button handlers surface a Page status message instead of silently doing nothing.
- Made draft recovery asynchronous during menu selection so restored local drafts are actually applied before render/fill/save state is computed.
- Added source regression coverage for the in-page dialog requirement and documented the Page save/button/render verification boundary.

### Testing
- `python -m unittest discover -s tests -v` -> 46 tests passed.
- `python -m compileall -q .` -> passed.
- Browser automation via `http://127.0.0.1:8771/.tmp-page-e2e/harness.html` with local Chrome -> passed: top new/save/copy/delete, style edit/copy/reset, section copy/delete, item add/edit/copy/delete, batch select/clear/enable/disable/layout/copy/delete, background upload/toggle, history restore, export/import, and no native dialogs. The only observed console 404 was the browser's unrelated static favicon request.
- Backend render-cache coverage already verifies every `DEFAULT_STYLE` field changes the render fingerprint and that save/list/status paths schedule or report render cache state.

### Notes
- `pages/menu-editor/app.js`：把原生确认/输入框替换为 Page 内弹窗，补齐异步按钮错误处理，并让本地草稿恢复在选择菜单时真正等待完成。
- `tests/test_menu_services.py`：新增 Page 按钮不依赖原生对话框的回归断言，并覆盖异步草稿恢复入口。
- `docs/page-editor-verification.md`：记录 Page 保存链路、按钮行为和后端渲染识别验证重点。
- `progress.md`：追加本轮修复、验证和回滚记录。
- 回滚方式：`git checkout -- pages/menu-editor/app.js tests/test_menu_services.py docs/page-editor-verification.md progress.md`；如已同步到本地 AstrBot，再从上一提交或远端分支重新复制插件文件到本地 AstrBot 插件目录。

## 2026-06-20 - Task: 修复 Page 控件首次改回默认值不触发渲染
### What was done
- 取消 Page 通用控件监听里的初始化值去重，确保控件首次改成 HTML 默认值时也会被识别。
- 覆盖“每行卡片改为 1 张”“关闭更新时间显示”“弹窗内自定义宽度/每行卡片后 Ctrl+S 保存”等配置链路，确认预览、已修改状态、保存 payload 和保存后预览一致。
- 补充回归说明，后续验证必须包含首次改回默认值的场景。
### Testing
- `python -m unittest tests.test_menu_services.MenuEditorSourceTests.test_page_buttons_use_resilient_bridge_and_change_events -v`：通过。
- `python -m unittest discover -s tests -v`：46 项通过。
- `python -m compileall -q .`：通过。
- Playwright + 本机 Chrome 打开 `http://127.0.0.1:8771/.tmp-page-e2e/harness.html`：验证隐藏 Page 控件首次改为 `columns=1` 会立即刷新预览并标记已修改；关闭 `showUpdatedAt` 后保存 payload 为 `show_updated_at=false`；弹窗内设置 `width_mode=custom,width=900,columns=3` 后 `Ctrl+S` 保存 payload 与保存后预览均为 900px/每行 3 张。
### Notes
- Changed files:
  - `pages/menu-editor/app.js`：移除通用控件监听的旧值去重，所有 input/change 都进入同步链路。
  - `tests/test_menu_services.py`：增加源码回归断言，防止恢复会吞掉默认值变更的旧去重逻辑。
  - `docs/page-editor-verification.md`：补充首次改回 HTML 默认值也必须即时生效的验证要求。
  - `progress.md`：追加本轮修复与验证记录。
- Rollback: `git revert <本轮提交>`，或将 `pages/menu-editor/app.js` 的 `bindValueChange` 恢复到上一个提交并同步回本地 AstrBot 插件目录。
- Local sync: 已复制本轮 4 个变更文件到 `C:\Users\21340\.astrbot_launcher\instances\263ca536-4cb7-4f22-b872-e68958ec3dc8\core\data\plugins\astrbot_plugin_bot_menu`，并用 SHA256 确认源/目标一致。
- Additional browser smoke after commit: Playwright + 本机 Chrome 复核新建、复制、删除未保存菜单、历史、导出、批量全选/启用/禁用/清除、添加分组、添加卡片、复制卡片、重置样式按钮均通过。

## 2026-06-20 - Task: 重构 Page 保存与实际渲染链路
### What was done
- 将 Page 保存改为提交当前完整菜单快照，避免保存时重新遍历弹窗旧控件导致已修改配置被旧值覆盖。
- 收紧后端保存入口，只接受 `{ "menu": ... }` 完整菜单对象；保存后继续以 canonical menu 刷新前端状态并调度渲染缓存。
- 删除独立旧渲染模板，实际浏览器/远程 HTML 渲染统一使用 Page 预览同形 HTML；非显式 `pillow` 模式不再静默回退到不一致的 Pillow 外观。
- 保留背景图只在上传、铺满、居中等用户明确动作时自动对齐；保存和渲染读取已保存的 `background_image_x/y/width`。
- 补充完整快照保存、背景偏移、渲染 HTML 同源的回归测试，并更新 Page 保存/渲染契约文档。
### Testing
- `python -m unittest tests.test_menu_services -v`：通过，47 项测试全部 OK。
- 临时集成脚本：保存包含背景偏移的菜单，检查 `build_preview_html` 包含 `left:11%;top:-27%;width:144%`，并通过 `render_menu_via_browser` 生成 PNG，输出 `OK browser render integration-browser-0deb75afac05.png bytes=33161`。
### Notes
- `pages/menu-editor/app.js`：保存改为克隆完整工作态快照；只刷新当前聚焦控件；样式弹窗变更后同步主表单控件，避免后续主表单事件覆盖已修改样式。
- `main.py`：保存接口改为完整菜单 payload；浏览器/远程 HTML 渲染失败时明确报错，不再默认用旧 Pillow 外观静默兜底。
- `services/renderer.py`：移除独立旧模板，保留 Page 预览 HTML 作为实际渲染唯一 HTML 来源。
- `tests/test_menu_services.py`：新增完整快照持久化与渲染同源测试，调整保存源码断言。
- `docs/page-editor-verification.md`：记录完整快照保存、渲染同源、背景图不自动回顶的契约。
- 回滚方式：使用 Git 回滚本轮修改文件，或从提交前状态恢复上述 5 个文件；若只需临时恢复旧渲染兜底，可先回滚 `main.py` 与 `services/renderer.py`。

## 2026-06-21 - Task: 修复 Page 样式在实际渲染图中回退默认值
### What was done
- 修复实际渲染 HTML 中 `.preview-card` 内联样式未做 HTML 属性转义的问题，避免字体族里的双引号截断后续 CSS 变量。
- 确认已保存的 Page 配置在渲染时被浏览器真实读取：当前默认菜单渲染宽度为 520px、每行 1 张、前景透明度为 0。
- 重新生成本地 AstrBot 默认菜单渲染缓存，覆盖旧的错误缓存图。
- 将修复文件同步到本地 AstrBot 插件目录，并补充渲染契约文档和回归测试。
### Testing
- `python -m unittest tests.test_menu_services.MenuStorageTests.test_preview_html_uses_page_preview_markup -v`：通过。
- `python -m unittest discover -s tests -v`：47 项通过。
- `python -m compileall -q .`：通过。
- 本机 Edge CDP 打开真实 `default` 菜单渲染 HTML：`.preview-card` style 未再截断，浏览器计算值为 `width=520px`、`--preview-columns=1`、`--preview-foreground-opacity=0.000`、`.preview-inner background=rgba(255, 255, 255, 0)`、`.preview-item background=rgba(241, 245, 249, 0)`。
- 使用真实本地 `menus.json` 重新生成 PNG：图片已呈现 1 列卡片和透明前景；本地缓存 `default-cached-201564b39ddcf950.png` 已更新为新渲染结果。
- 本地 AstrBot 同步校验：`services/renderer.py`、`tests/test_menu_services.py`、`docs/page-editor-verification.md` 源/目标 SHA256 一致。
### Notes
- `services/renderer.py`：对 `.preview-card` 的 style 属性使用 HTML 转义，修复渲染时 CSS 变量被双引号截断的问题。
- `tests/test_menu_services.py`：新增 HTMLParser 级断言，确保浏览器可解析的 style 属性中仍包含宽度、列数和前景透明度变量。
- `docs/page-editor-verification.md`：补充渲染 HTML 内联样式必须做属性转义的契约，防止保存正确但渲染回退默认值。
- `progress.md`：追加本轮修复、验证、同步和回滚记录。
- 回滚方式：`git checkout -- services/renderer.py tests/test_menu_services.py docs/page-editor-verification.md progress.md`；如需回滚本地 AstrBot，同步上一提交的同名文件到 `C:\Users\21340\.astrbot_launcher\instances\263ca536-4cb7-4f22-b872-e68958ec3dc8\core\data\plugins\astrbot_plugin_bot_menu`，并重新生成或删除对应渲染缓存。

## 2026-06-21 - Task: 修复背景图锁定后仍被自动上端对齐
### What was done
- 复现 Page 背景编辑竞态：背景图未加载完成时先触发自动铺满，随后用户拖动背景并点击“锁定背景图”，迟到的图片 `load` 回调仍会把 `background_image_y` 改回 0。
- 为背景自动铺满/适应增加图片来源、X、Y、宽度快照校验；只有当前背景变换仍与发起自动计算时一致，迟到的 `load` 回调才允许继续执行。
- 将同样保护应用到“适应背景”，避免同类异步回调覆盖用户手动位置。
- 补充回归断言和 Page 背景编辑契约文档。
### Testing
- `python -m unittest tests.test_menu_services.MenuStorageTests.test_page_reload_does_not_realign_saved_background_to_top -v`：通过。
- `python -m unittest discover -s tests -v`：47 项通过。
- `python -m compileall -q .`：通过。
- 本机 Edge CDP + `.tmp-page-e2e/harness.html` 慢加载背景图复现脚本：修复前锁定后结果为 `y=0/top=0%`；修复后拖到 `x=12,y=-37,width=140` 并点击“锁定背景图”，等待图片加载完成仍保持 `left=12%`、`top=-37%`、`width=140%`、`editMode=false`。
### Notes
- `pages/menu-editor/app.js`：为自动铺满/适应的异步图片加载回调增加背景变换快照保护，防止锁定后的手动位置被上端对齐覆盖。
- `tests/test_menu_services.py`：增加源码回归断言，确保延迟 `load` 回调必须携带并校验背景变换快照。
- `docs/page-editor-verification.md`：补充背景图未加载完成时自动计算不得覆盖用户拖动/锁定后位置的契约。
- `progress.md`：追加本轮修复、验证和回滚记录。
- 回滚方式：`git checkout -- pages/menu-editor/app.js tests/test_menu_services.py docs/page-editor-verification.md progress.md`；如已同步到本地 AstrBot，再把上一提交同名文件复制回 `C:\Users\21340\.astrbot_launcher\instances\263ca536-4cb7-4f22-b872-e68958ec3dc8\core\data\plugins\astrbot_plugin_bot_menu`。

## 2026-06-21 - Task: 深度复查背景锁定后回顶缩小冲突
### What was done
- 重新审计所有会写入 `background_image_x/y/width` 的 Page 前端路径，确认除迟到图片 `load` 回调外，背景拖动期间还存在 `ensureStyle()` 反复替换 `menu.style` 对象的引用冲突。
- 修复背景拖动/拉伸写入逻辑：每次 pointer move 都重新写入当前 `state.menu.style`，不再依赖进入编辑模式时捕获的旧 style 引用。
- 修复 `ensureStyle()`：只补齐缺失默认字段，不再无条件替换整个 `menu.style` 对象，避免拖动、锁定、重绘之间出现旧对象和当前工作态分叉。
- 为 Page 入口主脚本增加版本查询参数，降低 WebView 继续加载旧 `app.js` 导致用户仍看到旧行为的风险。
- 补充回归断言和背景编辑契约文档。
### Testing
- `python -m unittest tests.test_menu_services.MenuStorageTests.test_page_reload_does_not_realign_saved_background_to_top -v`：通过。
- `python -m unittest discover -s tests -v`：47 项通过。
- `python -m compileall -q .`：通过。
- 本机 Edge CDP + `.tmp-page-e2e/harness.html` 真实 pointer 拖动验证：连续两次拖动后，锁定前后工作态和 DOM 均保持约 `x=14,y=30,width=160`，不再只记录第一次移动值。
- 本机 Edge CDP 慢加载背景图验证：自动铺满挂起时手动设为 `x=12,y=-37,width=220` 并锁定，等待图片加载完成后仍保持 `left=12%`、`top=-37%`、`width=220%`、`editMode=false`，未回顶、未缩小。
### Notes
- `pages/menu-editor/app.js`：背景拖动/拉伸改为写当前 style；`ensureStyle()` 改为就地补默认字段，避免替换对象造成位置尺寸写丢。
- `pages/menu-editor/index.html`：为 `app.js` 增加版本参数，避免 WebView 继续使用旧脚本。
- `tests/test_menu_services.py`：补充背景锁定、style 引用稳定性和入口脚本版本参数断言。
- `docs/page-editor-verification.md`：补充背景拖动期间不得替换 `menu.style` 对象的契约。
- `progress.md`：追加本轮复查、修复、验证和回滚记录。
- 回滚方式：`git checkout -- pages/menu-editor/app.js pages/menu-editor/index.html tests/test_menu_services.py docs/page-editor-verification.md progress.md`；如已同步到本地 AstrBot，再把上一提交同名文件复制回 `C:\Users\21340\.astrbot_launcher\instances\263ca536-4cb7-4f22-b872-e68958ec3dc8\core\data\plugins\astrbot_plugin_bot_menu`。

## 2026-06-21 - Task: 修复 Page 拖动背景保存后与实际渲染位置不一致
### What was done
- 重新复查 Page 背景拖动、保存 payload、后端 HTML 构造和浏览器实际计算链路，确认保存的 `background_image_x/y/width` 值会被后端读取，但 Page 预览与实际渲染使用的布局高度不一致。
- 修复 Page 预览 `.preview-card` 内联 style 未转义的问题，避免默认字体栈中的双引号截断后续 `--preview-width` 等 CSS 变量，导致 Page 预览本身坐标系错误。
- 将 Page 和后端渲染的关键布局规则对齐：默认字体栈、标题字号、基础字号、外框 padding、内容层 padding、分组标题 margin，确保 `background_image_y` 百分比按同一容器高度计算。
- 补充回归断言，锁定 Page/后端背景坐标系一致性关键规则。
### Testing
- `python -m unittest tests.test_menu_services.MenuStorageTests.test_page_reload_does_not_realign_saved_background_to_top -v`：通过。
- `python -m unittest discover -s tests -v`：47 项通过。
- `python -m compileall -q .`：通过。
- 本机 Edge CDP 对同一菜单分别打开 Page 预览和后端 `build_preview_html`：修复前 Page 卡片高 `473px`、后端卡片高 `579px`，同样 `top:-37%` 实际偏移不同；修复后 Page 与后端均为 `592x482.390625`，背景图 left/top/width/height delta 全部为 0。
- 本机 Edge CDP 端到端验证：在 Page 里真实 pointer 拖动背景并保存，保存 payload 为 `background_image_x=15, background_image_y=-12, background_image_width=180`；用该保存 payload 生成后端实际渲染 HTML 后，Page 与后端背景图 `left/top/width/height` delta 全部为 0。
### Notes
- `pages/menu-editor/app.js`：Page 预览卡片 style 属性改为转义输出，并将无自定义字体时的默认预览字体栈与后端渲染保持一致。
- `pages/menu-editor/style.css`：固定 Page 预览标题字号，避免随编辑器窗口 `vw` 变化造成与实际渲染高度不一致。
- `services/renderer.py`：对齐实际渲染的基础字号、kicker、外框/内层 padding 和分组标题 margin，使背景百分比坐标使用与 Page 一致的容器高度。
- `services/render_cache.py`：提升渲染缓存版本，确保旧布局生成的图片缓存不会继续被复用。
- `pages/menu-editor/index.html`：更新 `app.js` 版本参数，避免 WebView 继续缓存旧预览逻辑。
- `tests/test_menu_services.py`：补充 Page/后端坐标系一致性源码断言。
- `docs/page-editor-verification.md`：补充 Page 与实际渲染必须共享影响背景百分比坐标的布局规则。
- `progress.md`：追加本轮复查、修复、验证和回滚记录。
- 回滚方式：`git checkout -- pages/menu-editor/app.js pages/menu-editor/style.css pages/menu-editor/index.html services/renderer.py services/render_cache.py tests/test_menu_services.py docs/page-editor-verification.md progress.md`；如已同步到本地 AstrBot，再把上一提交同名文件复制回 `C:\Users\21340\.astrbot_launcher\instances\263ca536-4cb7-4f22-b872-e68958ec3dc8\core\data\plugins\astrbot_plugin_bot_menu`。

## 2026-06-21 - Task: 同步 Page 背景位置修复到本地 AstrBot
### What was done
- 将 Page 背景位置一致性修复同步到本机 AstrBot 插件目录，并逐文件校验源仓库与本机插件 SHA256 一致。
- 清理本机插件目录内旧 `__pycache__`，避免运行时继续加载旧 Python 字节码。
- 复核本机插件数据的渲染缓存状态，确认缓存版本提升后现有菜单都会进入 `missing` 状态，下一次渲染会重新生成新布局图片。
### Testing
- SHA256 校验 8 个同步文件全部一致：`pages/menu-editor/app.js`、`pages/menu-editor/style.css`、`pages/menu-editor/index.html`、`services/renderer.py`、`services/render_cache.py`、`tests/test_menu_services.py`、`docs/page-editor-verification.md`、`progress.md`。
- 本机插件数据 `render_cache.json` 复核：`default`、`menu`、`menu_2`、`menu_3` 在新缓存指纹下均返回 `missing`，旧图不会被继续命中。
### Notes
- `progress.md`：追加本机 AstrBot 同步、缓存复核和回滚记录。
- 回滚方式：`git checkout -- progress.md`；如需回滚本机 AstrBot 同步，把上一提交同名文件复制回 `C:\Users\21340\.astrbot_launcher\instances\263ca536-4cb7-4f22-b872-e68958ec3dc8\core\data\plugins\astrbot_plugin_bot_menu`，并删除本机插件 `render_cache.json` 中本轮生成的新缓存条目或等待重新渲染覆盖。

## 2026-06-21 - Task: 完善菜单字体系统
### What was done
- 新增运行时用户字体目录解析：后端自动使用数据目录下的 `fonts/`，支持 `.ttf/.otf/.ttc/.woff/.woff2`，菜单只保存字体名或相对路径，不保存本机绝对路径。
- Page 初始化时加载后端字体列表和字体 CSS，字体族输入支持用户字体候选；保存后的 `font_family` 会被实际渲染 HTML 同链路读取。
- 实际浏览器渲染与远程 HTML 渲染都接入统一字体解析并注入 `@font-face`；Pillow 备用渲染也优先读取用户字体目录，不再依赖写死的 Windows 字体路径。
- 渲染缓存指纹加入选中字体文件签名，并提升缓存版本，替换字体文件后不会继续复用旧图。
- 补充字体系统说明文档和 Page/渲染链路验证约定。
### Testing
- `node --check pages/menu-editor/app.js`
- `python -m unittest discover -s tests -v`（50 tests OK）
- `python -m compileall -q .`
- `git diff --check`
- 手动渲染验证：临时复制本机字体到测试数据目录 `fonts/brand/VerifyFont.ttf`，`build_preview_html(..., font_registry=...)` 成功注入 `@font-face` 且未泄露临时绝对路径，`render_menu_via_browser(...)` 成功生成 PNG（30440 bytes）。
### Notes
- `services/fonts.py`：新增用户字体目录扫描、相对路径匹配、CSS 字体栈和字体文件签名能力。
- `services/renderer.py`：渲染 HTML 接入 FontRegistry，统一默认字体栈并注入选中用户字体。
- `services/local_image.py`：Pillow 备用渲染改为通过用户字体目录解析字体，移除写死的 Windows 字体路径候选。
- `services/render_cache.py`：缓存版本升到 4，并把选中用户字体文件签名纳入指纹。
- `services/__init__.py`：导出 FontRegistry。
- `main.py`：初始化字体注册表，新增 `fonts` API，并在实际渲染链路传入字体注册表。
- `pages/menu-editor/app.js`：Page 启动加载字体列表/CSS，字体族输入支持用户字体候选，预览字体栈从统一函数生成。
- `pages/menu-editor/style.css`：命令字体改走预览 CSS 变量，避免 Page 和后端字体栈分叉。
- `pages/menu-editor/index.html`：更新 app.js 版本参数，避免旧前端缓存。
- `tests/test_menu_services.py`：增加用户字体相对路径、渲染 HTML 注入字体、字体变化刷新缓存的回归测试。
- `docs/font-system.md`：新增字体目录、选择方式、渲染约定和跨环境要求说明。
- `docs/page-editor-verification.md`：补充字体渲染链路验证约定。
- `README.md`：补充用户字体使用入口。
- 回滚方式：执行 `git revert <本轮提交>`；未提交前可用 `git checkout -- README.md docs/page-editor-verification.md main.py pages/menu-editor/app.js pages/menu-editor/index.html pages/menu-editor/style.css services/__init__.py services/local_image.py services/render_cache.py services/renderer.py tests/test_menu_services.py` 并删除 `docs/font-system.md`、`services/fonts.py`。

## 2026-06-21 - Task: 同步字体系统到本地 AstrBot
### What was done
- 将本轮字体系统相关代码、文档、测试和进度日志同步到本地 AstrBot 插件目录。
- 确保本地运行数据目录存在 `plugin_data/astrbot_plugin_bot_menu/fonts/`，供用户直接放入自定义字体文件。
### Testing
- SHA256 校验 14 个同步文件，源仓库与本地 AstrBot 插件目录完全一致。
- 清理本地插件目录下 `__pycache__`。
### Notes
- `C:\Users\21340\.astrbot_launcher\instances\263ca536-4cb7-4f22-b872-e68958ec3dc8\core\data\plugins\astrbot_plugin_bot_menu`：同步本轮修改后的插件文件。
- `C:\Users\21340\.astrbot_launcher\instances\263ca536-4cb7-4f22-b872-e68958ec3dc8\core\data\plugin_data\astrbot_plugin_bot_menu\fonts`：创建/确认用户字体目录。
- 回滚方式：重新从目标分支同步上一提交文件，或在本地 AstrBot 插件目录执行相同文件的反向拷贝；用户字体目录为空目录时可直接删除。
