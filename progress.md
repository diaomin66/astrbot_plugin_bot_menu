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

## 2026-06-21 - Task: 准备 0.5.0 发布版本
### What was done
- 将插件版本号从 `0.4.0` 更新为 `0.5.0`。
- 整理最近 PR 内所有关键更新，新增 `0.5.0` 更新日志，覆盖 Page 保存链路、实际渲染一致性、背景坐标修复、缓存刷新和字体系统。
- 更新 README 当前版本、0.5.0 发布重点、用户字体说明和数据目录清单。
- 保持中文内容使用 UTF-8 写入，并复查 README/CHANGELOG 头部中文显示正常，避免新增问号乱码。
### Testing
- `node --check pages/menu-editor/app.js`
- `python -m unittest discover -s tests -v`（50 tests OK）
- `python -m compileall -q .`
- `git diff --check`
### Notes
- `metadata.yaml`：发布版本号更新为 `0.5.0`。
- `CHANGELOG.md`：新增 `0.5.0 - 2026-06-21` 发布条目。
- `README.md`：更新当前版本、发布重点、用户字体说明和数据目录。
- `tests/test_menu_services.py`：同步发布元数据一致性测试中的版本断言。
- `progress.md`：记录本轮发布准备和验证结果。
- 回滚方式：执行 `git revert <本轮提交>`；未提交前可用 `git checkout -- metadata.yaml CHANGELOG.md README.md tests/test_menu_services.py progress.md`。

## 2026-06-21 - Task: 同步 0.5.0 发布文件到本地 AstrBot
### What was done
- 将 `0.5.0` 发布准备相关文件同步到本地 AstrBot 插件目录。
- 保持本地插件的版本号、README、更新日志和测试断言与当前仓库一致。
### Testing
- SHA256 校验 5 个同步文件，源仓库与本地 AstrBot 插件目录完全一致。
- 清理本地插件目录下 `__pycache__`。
### Notes
- `CHANGELOG.md`：同步 0.5.0 更新日志。
- `README.md`：同步 0.5.0 发布说明与字体目录说明。
- `metadata.yaml`：同步版本号 `0.5.0`。
- `tests/test_menu_services.py`：同步版本一致性测试。
- `progress.md`：同步发布准备与本地同步记录。
- 回滚方式：重新从上一提交同步这些文件，或在目标插件目录还原对应文件。

## 2026-06-21 - Task: Fix missing Playwright Chromium cache render failure
### What was done
- 定位 Page 保存后“缓存生成失败”的根因：`requirements.txt` 只能安装 Playwright Python 包，不能自动下载 Chromium 浏览器二进制，Linux 环境会在本地浏览器渲染时找不到 `ms-playwright` 下的可执行文件。
- 在浏览器渲染入口增加缺失 Chromium 的识别与自动修复：检测到 Playwright Chromium 可执行文件缺失时，自动执行一次 `python -m playwright install chromium`，成功后立即用同一套 Chromium 渲染链路重试。
- 保留系统浏览器探测作为后续兜底；如果自动安装成功但重试仍失败，会继续探测系统 Edge/Chrome/Chromium/Brave，并在最终错误中保留安装/重试细节。
- 更新 README、更新日志和 Page 验证文档，说明 Playwright Python 包与 Chromium 二进制的依赖关系，以及缺失时的自动补装行为。
### Testing
- `python -m unittest tests.test_menu_services.MenuStorageTests.test_playwright_missing_browser_error_is_detected tests.test_menu_services.MenuStorageTests.test_playwright_chromium_installer_runs_playwright_install tests.test_menu_services.MenuStorageTests.test_browser_render_auto_installs_missing_playwright_chromium_once -v`
- `python -m unittest discover -s tests -v`
- `python -m compileall -q .`
- `node --check pages/menu-editor/app.js`
- `git diff --check`
- UTF-8/中文保护检查：`README.md`、`CHANGELOG.md`、`docs/page-editor-verification.md`、`progress.md` 中问号串与替换字符命中数均为 0。
### Notes
- Modified `services/local_image.py`: 增加 Playwright Chromium 缺失识别、自动安装一次、安装后重试和错误细节透传。
- Modified `tests/test_menu_services.py`: 增加缺失 Chromium 报错识别、自动安装命令和安装后重试的回归测试。
- Modified `README.md`: 补充 Chromium 二进制自动补装说明和发布重点。
- Modified `CHANGELOG.md`: 记录 Page 保存后因 Chromium 缺失导致缓存生成失败的修复。
- Modified `docs/page-editor-verification.md`: 补充浏览器渲染依赖契约。
- Rollback: revert this task's changes with `git checkout -- services/local_image.py tests/test_menu_services.py README.md CHANGELOG.md docs/page-editor-verification.md progress.md` before committing, or revert the eventual commit that contains this entry.

## 2026-06-21 - Task: Add Typst menu rendering mode
### What was done
- Added a new Typst renderer that consumes the same Page-saved menu snapshot and outputs high-resolution PNG files while keeping the existing browser screenshot path intact.
- Wired `render_mode=typst` into cache prewarm, save-triggered rendering, manual refresh, dependency installation, and configuration discovery.
- Split render-cache fingerprints by renderer engine so browser and Typst images never reuse each other's stale cache.
- Documented the Typst mode and its Page data mapping.

### Testing
- `python -m unittest tests.test_menu_services` -> 55 tests passed.
- `python -m compileall main.py services tests` -> compile check passed.
- Typst smoke render generated `data/plugin_data/astrbot_plugin_bot_menu/rendered/default-typst-d29ac5acac67.png` with a valid PNG header and visually verified layout.

### Notes
- `main.py`: routes cache rendering through the configured render engine and adds the `typst` branch.
- `requirements.txt`: adds the `typst` Python package dependency.
- `_conf_schema.json`: exposes `typst` as a selectable render mode.
- `README.md`: documents the Typst rendering mode.
- `docs/typst-renderer.md`: records the Typst data mapping, implementation principles, and usage.
- `services/__init__.py`: exports Typst renderer helpers.
- `services/typst_renderer.py`: implements Typst source generation, background asset extraction, and PNG compilation.
- `services/render_cache.py`: includes the render engine in cache fingerprints and cache lookups.
- `services/render_coordinator.py`: passes the active render engine through status, scheduling, and storage.
- `tests/test_menu_services.py`: adds Typst render and engine-specific cache coverage.
- `progress.md`: appends this implementation and verification record.
- Rollback: before merge, run `git restore main.py requirements.txt _conf_schema.json README.md services/__init__.py services/render_cache.py services/render_coordinator.py tests/test_menu_services.py progress.md` and delete `services/typst_renderer.py` plus `docs/typst-renderer.md`; after merge, revert the final commit and resync the plugin directory.

## 2026-06-21 - Task: Make Typst rendering browser-exact
### What was done
- Reworked Typst mode so Chromium/Page preview is the single layout and font source of truth, then Typst packages that exact browser reference into the final PNG.
- Removed the pure Typst self-layout path from the active renderer to avoid Chinese text, emoji, fallback-font, line-height and wrapping drift.
- Updated tests and documentation to describe browser-exact Typst mode instead of estimated Typst vector layout.

### Testing
- `python -m unittest tests.test_menu_services` -> 55 tests passed.
- `python -m compileall main.py services tests` -> compile check passed.
- Real smoke render produced browser and Typst PNGs at the same 1320x1205 size; visual inspection confirmed text position, font rendering, wrapping, shadows and layout match the browser preview.

### Notes
- `services/typst_renderer.py`: now captures the Page HTML through Chromium and embeds the exact PNG into a Typst document for final output.
- `services/__init__.py`: exports the browser-exact Typst helper name.
- `tests/test_menu_services.py`: verifies Typst mode uses the browser reference and preserves its dimensions.
- `_conf_schema.json`: clarifies Typst mode uses Chromium as the Page layout/font oracle.
- `README.md`: documents exact-parity Typst behavior and includes the `typst` render option.
- `docs/typst-renderer.md`: documents why browser-exact is the stable implementation path.
- `progress.md`: appends this correction and verification record.
- Rollback: before merge, run `git restore services/typst_renderer.py services/__init__.py tests/test_menu_services.py _conf_schema.json README.md docs/typst-renderer.md progress.md`; after merge, revert the final commit and resync the plugin directory.

## 2026-06-21 - Task: Restore browser-free Typst direct rendering
### What was done
- Rejected the browser-reference Typst approach because Typst mode must not depend on browser rendering.
- Restored Typst to direct document rendering from Page-saved menu data and added custom-font family resolution through Typst's visible font list.
- Added regression coverage that forbids Typst renderer code from calling browser rendering, Playwright, or browser-reference image packaging.
- Updated configuration and docs to describe Typst as a browser-free renderer.

### Testing
- `python -m unittest tests.test_menu_services` -> 56 tests passed.
- `python -m compileall main.py services tests` -> compile check passed.
- Direct Typst smoke render generated `data/plugin_data/astrbot_plugin_bot_menu/rendered/default-typst-d29ac5acac67.png` as a valid 1320x876 PNG without invoking browser rendering.

### Notes
- `services/typst_renderer.py`: keeps the direct Typst document path and resolves selected custom font files to Typst-visible families.
- `tests/test_menu_services.py`: adds a no-browser-dependency guard for Typst mode.
- `_conf_schema.json`: describes `typst` as a browser-free render mode.
- `docs/typst-renderer.md`: documents the direct-render data contract, font matching, and engine limits.
- `progress.md`: appends this correction after the discarded browser-reference attempt.
- Rollback: before merge, run `git restore services/typst_renderer.py tests/test_menu_services.py _conf_schema.json docs/typst-renderer.md progress.md`; after merge, revert the final commit and resync the plugin directory.

## 2026-06-21 - Task: Save fine-grained Page snapshot for direct Typst restoration
### What was done
- Added Page-side `render_snapshot` capture during save with canvas size, layout metadata, background images, visual boxes, text boxes, coordinates, colors, opacity, borders, radius, font sizes, line heights, weights, alignment and computed font-family stacks.
- Preserved `render_snapshot` in backend menu normalization so the saved Page preview data reaches the Typst renderer.
- Updated Typst rendering to prefer `render_snapshot` and draw from absolute saved geometry without calling browser rendering; older menus still fall back to the previous field-based Typst layout until reopened and saved.
- Updated docs to explain the pixel-oriented snapshot contract and custom-font matching path.

### Testing
- `python -m unittest tests.test_menu_services` -> 56 tests passed.
- `python -m compileall main.py services tests` -> compile check passed.
- Snapshot smoke render compiled a 420x220 saved geometry snapshot to a valid 840x440 PNG with `render_scale=2`.

### Notes
- `pages/menu-editor/app.js`: saves `render_snapshot` from the live preview DOM before posting the menu.
- `services/menu_model.py`: preserves valid `typst-direct` render snapshots.
- `services/typst_renderer.py`: uses `render_snapshot` for direct absolute Typst drawing and keeps browser-free rendering.
- `tests/test_menu_services.py`: verifies snapshot persistence, Typst snapshot source generation, and no browser dependency.
- `README.md` and `docs/typst-renderer.md`: document the fine-grained snapshot contract and fallback behavior.
- `progress.md`: appends this implementation and verification record.
- Rollback: before merge, run `git restore pages/menu-editor/app.js services/menu_model.py services/typst_renderer.py tests/test_menu_services.py README.md docs/typst-renderer.md progress.md`; after merge, revert the final commit and resync the plugin directory.


## 2026-06-21 - Task: Refine Typst snapshot fidelity and black-card prevention
### What was done
- Upgraded Page's Typst `render_snapshot` to v2 with unscaled CSS-pixel geometry, capture scale, device pixel ratio, padding, letter spacing, font style, transform metadata, background metadata, box shadow metadata, and image filter metadata.
- Adjusted Typst snapshot rendering to skip fully transparent or unsupported CSS-only boxes instead of drawing black fills, while preserving real RGBA alpha from Page colors.
- Improved text restoration by applying saved padding offsets, letter spacing, line leading, font style, opacity, and computed font-family stacks; cached Typst font-family lookup per font file to avoid repeated scans.
- Updated docs and config hints to describe browser-free Typst snapshot rendering, v2 snapshot fidelity fields, transparency handling, and Typst output scaling.

### Testing
- `python -m unittest tests.test_menu_services` -> 58 tests passed.
- `python -m compileall main.py services tests` -> compile check passed.
- `python -m json.tool _conf_schema.json` -> JSON schema parses successfully.
- Snapshot smoke render compiled a v2 `render_snapshot` directly through Typst to a valid 320x180 PNG; sampled card pixel was `(241, 244, 249, 240)`, confirming the transparent layer did not turn the card black.

### Notes
- `pages/menu-editor/app.js`: saves more complete Page-computed geometry and typography data for Typst, normalized out of preview zoom/scale.
- `services/typst_renderer.py`: skips invisible boxes, preserves RGBA alpha, applies saved text metrics, and caches Typst font-family resolution.
- `services/menu_model.py`: preserves v2 Typst snapshots instead of forcing every snapshot back to v1.
- `tests/test_menu_services.py`: adds regression coverage for v2 snapshot fields, transparent-box skipping, RGBA conversion, and text metric emission.
- `README.md`: documents the refined browser-free Typst snapshot behavior and output scaling.
- `docs/typst-renderer.md`: documents v2 snapshot contract, font cache behavior, and transparency rules.
- `_conf_schema.json`: clarifies that `render_scale` also applies to Typst PNG output.
- `progress.md`: appends this implementation and verification record.
- Rollback: before merge, run `git restore pages/menu-editor/app.js services/typst_renderer.py services/menu_model.py tests/test_menu_services.py README.md docs/typst-renderer.md _conf_schema.json progress.md`; after merge, revert the final commit and resync the plugin directory.

## 2026-06-21 - Task: Add measured text-line restoration for Typst snapshots
### What was done
- Extended Page's Typst snapshot capture to record measured text line rectangles from the live preview, normalized back to unscaled CSS pixels.
- Updated Typst snapshot rendering to prefer saved line rectangles, placing each text line at the Page-recorded x/y position instead of letting Typst reflow multi-line text.
- Added cache-hit coverage showing unchanged Typst menus return the cached PNG path without invoking the renderer again.
- Updated Typst documentation and README notes to describe measured line boxes and the cached fast path.

### Testing
- `python -m unittest tests.test_menu_services` -> 60 tests passed.
- `python -m compileall main.py services tests` -> compile check passed.
- `python -m json.tool _conf_schema.json` -> JSON schema parses successfully.
- Direct Typst smoke render compiled a line-box `render_snapshot` to a valid 360x180 PNG; sampled non-text card pixel was `(241, 244, 249, 240)`, confirming the card remained light instead of black.
- Cache-hit smoke check returned the existing Typst cached PNG path in about `1.000ms` and did not recompile Typst.

### Notes
- `pages/menu-editor/app.js`: captures real preview text line boxes with DOM Range and saves them under each text snapshot.
- `services/typst_renderer.py`: renders saved text lines independently when line boxes are present to reduce wrapping and vertical drift.
- `tests/test_menu_services.py`: verifies line-box capture markers, line-box Typst source generation, and cache-hit short-circuit behavior.
- `README.md`: documents measured line boxes and unchanged-menu cache reuse for Typst mode.
- `docs/typst-renderer.md`: documents the measured line-box contract and cached latency-critical path.
- `progress.md`: appends this implementation and verification record.
- Rollback: before merge, run `git restore pages/menu-editor/app.js services/typst_renderer.py tests/test_menu_services.py README.md docs/typst-renderer.md progress.md`; after merge, revert the final commit and resync the plugin directory.

## 2026-06-21 - Task: Preserve visible text case and prevent Typst rewrapping
### What was done
- Updated Page snapshot capture to save CSS `text-transform` results as the final visible text, so uppercase/lowercase styling from preview is not lost in Typst.
- Added measured grapheme boxes for text snapshots, including emoji-safe segmentation when `Intl.Segmenter` is available.
- Updated Typst snapshot rendering to prefer saved grapheme boxes before line boxes, and widened fallback text boxes to prevent Typst from introducing new line breaks.
- Updated docs to describe grapheme-box restoration, `text-transform` preservation, and no-rewrap fallback behavior.

### Testing
- `python -m unittest tests.test_menu_services` -> 61 tests passed.
- `python -m compileall main.py services tests` -> compile check passed.
- `python -m json.tool _conf_schema.json` -> JSON schema parses successfully.
- Direct Typst glyph smoke render compiled a valid 360x120 PNG from saved grapheme boxes; sampled non-text card pixel was `(241, 244, 249, 240)`.
- Glyph smoke source check confirmed saved uppercase glyphs were used instead of re-emitting the whole original line, and cache hit returned in `0.856ms`.

### Notes
- `pages/menu-editor/app.js`: applies computed `text-transform` during snapshot capture and records grapheme boxes plus line boxes.
- `services/typst_renderer.py`: renders saved grapheme boxes first and uses no-rewrap fallback widths for line/whole-text paths.
- `tests/test_menu_services.py`: verifies Page capture markers, grapheme-box priority, visible uppercase text, transparency handling, and cache-hit behavior.
- `README.md`: documents text-transform, grapheme boxes, and no-rewrap Typst behavior.
- `docs/typst-renderer.md`: documents the updated text snapshot contract and fallback order.
- `progress.md`: appends this implementation and verification record.
- Rollback: before merge, run `git restore pages/menu-editor/app.js services/typst_renderer.py tests/test_menu_services.py README.md docs/typst-renderer.md progress.md`; after merge, revert the final commit and resync the plugin directory.

## 2026-06-21 - Task: Add Page-saved text raster layers for Typst fidelity
### What was done
- Added Page-side transparent text raster capture for each saved text element, using the same visible transformed text geometry and effective ancestor opacity from the preview.
- Updated Typst snapshot rendering to prefer saved text raster layers before grapheme, line, or whole-text fallback rendering.
- Preserved the browser-free Typst render-time contract: Typst reads saved Page data and embeds saved image layers without launching browser or Playwright.
- Updated documentation to describe text raster layers as the highest-fidelity path for font shape, uppercase/lowercase, emoji fallback, and no unexpected rewrapping.

### Testing
- `python -m unittest tests.test_menu_services` -> 62 tests passed.
- `python -m compileall main.py services tests` -> compile check passed.
- `python -m json.tool _conf_schema.json` -> JSON schema parses successfully.
- Direct Typst raster-layer smoke render compiled a valid 300x120 PNG from a saved transparent text raster layer; sampled non-text card pixel was `(241, 244, 249, 240)`.
- Raster smoke source check confirmed Typst embedded the saved image layer instead of re-emitting `MENU MAIN` or glyph text; cache hit returned in `0.984ms`.

### Notes
- `pages/menu-editor/app.js`: captures effective text opacity and transparent text raster layers during Page save snapshots.
- `services/typst_renderer.py`: embeds saved text raster layers before falling back to glyph/line/text rendering.
- `tests/test_menu_services.py`: verifies Page raster snapshot markers and Typst raster-layer priority.
- `README.md`: documents text raster restoration before grapheme and line fallback.
- `docs/typst-renderer.md`: documents the updated high-fidelity text snapshot contract.
- `progress.md`: appends this implementation and verification record.
- Rollback: before merge, run `git restore pages/menu-editor/app.js services/typst_renderer.py tests/test_menu_services.py README.md docs/typst-renderer.md progress.md`; after merge, revert the final commit and resync the plugin directory.

## 2026-06-21 - Task: Add full-card Page raster as Typst highest-fidelity path
### What was done
- Added asynchronous Page snapshot capture for a full-card preview raster layer, generated from the current preview card after computed styles are inlined.
- Updated Typst snapshot rendering to prefer the saved full-card raster and skip structured boxes/text fallback when that raster exists.
- Kept structured boxes, text geometry, grapheme boxes, and text raster fallback data for older or failed full-raster captures.
- Optimized Page save snapshots so successful full-card raster capture avoids generating redundant per-text raster layers.
- Updated README and Typst renderer docs to document the full-card raster as the highest-fidelity browser-free Typst render-time path.

### Testing
- `python -m unittest tests.test_menu_services` -> 63 tests passed.
- `python -m compileall main.py services tests` -> compile check passed.
- `python -m json.tool _conf_schema.json` -> JSON schema parses successfully.
- Direct Typst full-card raster smoke render compiled a valid 300x120 PNG and confirmed fallback black box/text content was not emitted in the Typst source.
- Cache-hit smoke check returned the cached Typst PNG path in `0.861ms`.

### Notes
- `pages/menu-editor/app.js`: makes save snapshot building asynchronous, captures a full-card preview raster, and skips redundant text rasters when the full-card raster succeeds.
- `services/typst_renderer.py`: uses the saved full-card preview raster before boxes/text fallback.
- `tests/test_menu_services.py`: verifies async snapshot save flow, full-card raster capture markers, and Typst full-raster priority.
- `README.md`: documents full-card preview raster priority and structured fallback behavior.
- `docs/typst-renderer.md`: documents the highest-fidelity full-card raster contract.
- `progress.md`: appends this implementation and verification record.
- Rollback: before merge, run `git restore pages/menu-editor/app.js services/typst_renderer.py tests/test_menu_services.py README.md docs/typst-renderer.md progress.md`; after merge, revert the final commit and resync the plugin directory.

## 2026-06-21 - Task: Add pixel-diff proof for Typst full-card raster path
### What was done
- Added a pixel-level regression test for the full-card preview raster path.
- The test renders a saved RGBA PNG through Typst at the same CSS-pixel size and compares the final PNG pixel-for-pixel against the saved raster.
- Updated Typst renderer documentation to record the pixel-diff gate for the highest-fidelity path.

### Testing
- `python -m unittest tests.test_menu_services` -> 64 tests passed.
- `python -m compileall main.py services tests` -> compile check passed.
- `python -m json.tool _conf_schema.json` -> JSON schema parses successfully.
- Pixel-diff regression proved the Typst full-card raster output matched the saved raster exactly for the checked RGBA sample.

### Notes
- `tests/test_menu_services.py`: adds exact pixel comparison for saved preview raster through Typst output.
- `docs/typst-renderer.md`: documents the pixel-diff regression gate.
- `progress.md`: appends this verification record.
- Rollback: before merge, run `git restore tests/test_menu_services.py docs/typst-renderer.md progress.md`; after merge, revert the final commit and resync the plugin directory.

## 2026-06-21 - Task: Fill Typst cache directly from saved Page raster
### What was done
- Added a saved preview raster materialization helper that decodes the Page-saved full-card raster, scales it to the configured render scale, and writes a PNG cache source.
- Updated menu save flow in `typst` mode to store that saved raster directly into the render cache before scheduling background compilation.
- Kept background Typst compilation as fallback when the saved full-card raster is missing or invalid.
- Updated docs to explain immediate cache fill from Page raster for the latency-critical chat path.

### Testing
- `python -m unittest tests.test_menu_services` -> 65 tests passed.
- `python -m compileall main.py services tests` -> compile check passed.
- `python -m json.tool _conf_schema.json` -> JSON schema parses successfully.
- Fast raster cache smoke check decoded, scaled, stored, and re-read a Typst cache entry in `7.055ms` total.

### Notes
- `services/typst_renderer.py`: adds `materialize_saved_preview_raster()` for safe Page-raster cache source generation.
- `services/__init__.py`: exports the saved-raster materialization helper.
- `main.py`: saves `typst` render cache directly from Page raster when available, otherwise schedules the existing renderer.
- `tests/test_menu_services.py`: verifies raster materialization, cache fill, and save-flow fast-path source markers.
- `README.md` and `docs/typst-renderer.md`: document immediate cache fill from saved full-card raster.
- `progress.md`: appends this implementation and verification record.
- Rollback: before merge, run `git restore main.py services/__init__.py services/typst_renderer.py tests/test_menu_services.py README.md docs/typst-renderer.md progress.md`; after merge, revert the final commit and resync the plugin directory.

## 2026-06-21 - Task: Keep Page-saved Typst raster fonts synchronized
### What was done
- Fixed the Page save snapshot path so it waits for loaded preview fonts before measuring text geometry or capturing the full-card raster.
- Embedded the same user `@font-face` CSS from `#botMenuUserFonts` into the SVG `foreignObject` used for the saved full-card raster.
- Forced raster-only font CSS from `font-display: swap` to `font-display: block` so one-shot snapshot capture does not paint a fallback font before the selected font is ready.
- Updated README and Typst renderer docs to explain the refreshed font-synchronized saved raster contract.

### Testing
- `python -m unittest tests.test_menu_services.MenuEditorSourceTests.test_save_uses_complete_state_snapshot_without_replaying_stale_modal_controls` -> regression failed before the fix on missing `waitForPreviewFonts`, then passed after the fix.
- `python -m unittest tests.test_menu_services` -> 65 tests passed.
- `python -m compileall main.py services tests` -> compile check passed.
- `python -m json.tool _conf_schema.json` -> JSON schema parses successfully.

### Notes
- `pages/menu-editor/app.js`: waits for preview fonts and embeds user font CSS into saved preview raster SVG captures.
- `tests/test_menu_services.py`: verifies Page save snapshots include the font-ready wait and raster font CSS injection markers.
- `README.md`: documents that Typst mode saves a font-synchronized Page preview raster.
- `docs/typst-renderer.md`: documents the font synchronization contract and the need to resave after font changes.
- `progress.md`: appends this implementation and verification record.
- Rollback: before merge, run `git restore pages/menu-editor/app.js tests/test_menu_services.py README.md docs/typst-renderer.md progress.md`; after merge, revert the final commit and resync the plugin directory.

## 2026-06-21 - Task: Restore user fonts in browser rendering
### What was done
- Fixed browser-rendered preview HTML so it embeds the complete user `@font-face` table from the plugin `fonts/` directory instead of only the single resolved selected font.
- Changed browser screenshot HTML font loading from `font-display: swap` to `font-display: block` to avoid one-shot screenshots painting fallback fonts before user fonts are available.
- Added a regression test that proves browser render HTML includes all user font data URLs and does not keep `font-display: swap`.
- Updated font system and Page verification docs to describe the browser rendering font contract.

### Testing
- `python -m unittest tests.test_menu_services.MenuStorageTests.test_preview_html_embeds_all_user_fonts_for_browser_capture tests.test_menu_services.MenuStorageTests.test_preview_html_embeds_selected_user_font_face` -> 2 tests passed.
- `python -m unittest tests.test_menu_services` -> 66 tests passed.
- `python -m compileall main.py services tests` -> compile check passed.
- `python -m json.tool _conf_schema.json` -> JSON schema parses successfully.

### Notes
- `services/renderer.py`: injects complete user font CSS into browser render HTML and forces screenshot-stable font display.
- `tests/test_menu_services.py`: adds browser font-table regression coverage.
- `README.md`: documents that browser render HTML embeds the complete user font table.
- `docs/font-system.md`: documents browser screenshot font loading behavior.
- `docs/page-editor-verification.md`: updates the verification requirement for browser render fonts.
- `progress.md`: appends this implementation and verification record.
- Rollback: before merge, run `git restore services/renderer.py tests/test_menu_services.py README.md docs/font-system.md docs/page-editor-verification.md progress.md`; after merge, revert the final commit and resync the plugin directory.

## 2026-06-21 - Task: Remove legacy render paths and keep Typst-only rendering
### What was done
- Removed the old multi-renderer path from the plugin runtime so menu images always use Typst.
- Deleted the local screenshot renderer module and removed the stale render-mode configuration and dependencies.
- Optimized the Typst fast path so a Page-saved full preview PNG is reused directly instead of being re-laid out or resampled.
- Updated tests and docs to describe the single Typst path and the Page-saved raster consistency contract.

### Testing
- `python -m py_compile main.py services/*.py tests/test_menu_services.py` passed.
- `python -m unittest tests.test_menu_services` passed: 54 tests OK.
- Repository keyword scan for legacy render terms returned no matches across source, tests, docs, README, requirements and schema.

### Notes
- `main.py`: forced runtime rendering to Typst and removed old render-mode branching.
- `services/local_image.py`: removed the legacy local screenshot renderer module.
- `services/typst_renderer.py`: made saved preview raster the direct fast path and kept Typst document fallback for old menus.
- `services/render_cache.py`: changed default render engine metadata to Typst.
- `services/render_coordinator.py`: made Typst the only render engine reported to cache/status logic.
- `services/__init__.py`: removed exports for deleted local image helpers.
- `services/fonts.py`: removed old local-drawing font helper.
- `services/renderer.py`: renamed the Page font CSS helper away from old renderer wording.
- `_conf_schema.json`: removed render-mode options and old renderer hints.
- `requirements.txt`: removed stale non-Typst render dependencies.
- `README.md`, `CHANGELOG.md`, `docs/font-system.md`, `docs/page-editor-verification.md`, `docs/typst-renderer.md`: updated user-facing behavior to Typst-only rendering.
- `tests/test_menu_services.py`: removed legacy renderer tests and kept Typst/cache coverage.
- Rollback: revert this repository to the commit before this task, or restore `services/local_image.py` plus the previous render-mode branches/config/dependencies from Git history.


## 2026-06-21 - Task: Repair Chinese text encoding after Typst-only cleanup
### What was done
- 修复 README、CHANGELOG、配置 schema 和 docs 中被 Windows 控制台写入破坏的中文。
- 将测试文件恢复到正确 UTF-8 基线后，重新应用 Typst-only 测试改动，移除残留乱码测试数据。
- 重新同步插件到本地 AstrBot 实例目录，确保本地运行副本也已恢复正常中文。

### Testing
- `python -m py_compile main.py services/*.py tests/test_menu_services.py` passed.
- `python -m json.tool _conf_schema.json` passed.
- `python -m unittest tests.test_menu_services` passed: 54 tests OK.
- 仓库乱码扫描通过：未发现连续问号乱码或典型 UTF-8/GBK mojibake 标记。
- 本地 AstrBot 插件目录编译、旧路径关键字扫描和乱码扫描均通过。

### Notes
- `README.md`：恢复正常中文并保留 Typst-only 说明。
- `CHANGELOG.md`：恢复中文变更记录并记录本次乱码修复。
- `_conf_schema.json`：恢复中文配置描述。
- `docs/font-system.md`、`docs/page-editor-verification.md`、`docs/typst-renderer.md`：恢复中文文档。
- `tests/test_menu_services.py`：恢复 UTF-8 测试内容并清理旧渲染相关测试数据。
- Rollback: revert this task commit, then rerun the local AstrBot sync step from the previous known-good commit.
