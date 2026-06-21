# AstrBot Bot 菜单插件

一个用于自定义机器人菜单的 AstrBot 插件：在 WebUI 中编辑多套菜单方案，实时预览，并通过聊天指令发送渲染后的菜单图片。

- 当前版本：`0.5.0`
- 作者：雪碧bir
- 交流与反馈：**[点击加入 QQ 群 1081773675](https://qm.qq.com/q/Qr45Vz0a8o)**

## 0.5.0 发布重点

- Page 保存到实际渲染链路重新收敛：保存时强制读取当前页面完整状态，避免弹窗未失焦、默认值未改动或背景编辑状态导致实际图片沿用旧值。
- 背景图坐标一致性修复：Page 预览和实际浏览器渲染共享影响布局高度的规则，拖动/缩放背景后保存，实际图片按同一坐标系渲染。
- 样式变量安全修复：预览和渲染的内联 style 做属性转义，避免字体族中的引号截断每行卡片数、前景透明度、宽度等 CSS 变量。
- 渲染缓存刷新增强：布局、背景、样式和字体变化都会进入缓存指纹，旧图不会继续命中。
- 字体系统完善：运行数据目录自动提供 `fonts/`，用户可放入 `.ttf/.otf/.ttc/.woff/.woff2`，Page 按文件名或相对路径选择，实际渲染读取同一字体。

## 效果图

<img width="1280" height="1068" alt="c029cb7bdef068975a557a60a2644e8a_720" src="https://github.com/user-attachments/assets/67f9865b-3327-448b-88f6-26958f5c14c6" />

## 功能

- 插件 Pages 页面：`menu-editor`
- 多菜单方案：支持流畅新建、复制、删除、菜单切换、导入、导出（含内联资产包），导入前预览新增/覆盖/资产统计
- 背景资产：背景图保存到本地资产库并按 hash 去重，旧菜单内联背景继续兼容；Page 不再展示单独资产中心，减少编辑入口拥挤
- 可视化编辑：标题、副标题、分组、菜单项、图标、指令、描述、启用状态，支持分组和菜单项复制、上移、下移、折叠、桌面拖拽排序
- 编辑安心体验：未保存状态提示、本地草稿自动保存与恢复/丢弃提示、切换/新建/复制前自动保留当前草稿、保存/删除前自动快照、历史版本与已删除菜单一键恢复
- 大菜单运营：前端即时校验、保存前滚动到首个错误、分组/菜单项折叠状态记忆、菜单项搜索过滤、批量选择/启用/禁用/复制/删除/移动
- 效率工具：撤销/重做、Ctrl+S 保存、Ctrl+Z/Y 撤销重做、`/` 聚焦搜索；编辑器固定为紧凑密度和原比例预览
- 样式配置：10 个主题预设（含莫兰迪、马卡龙等柔和色系）、主色、背景色、自定义背景图（不限上传尺寸）、前景菜单透明度（0%-100%）、卡片色、文字色、辅助文字色、字体、阴影、边框、水印、智能/手动宽度、每行卡片数、智能/自定义分组间距（0-200，0 为完全贴合）、圆角、更新时间
- 用户字体：运行时数据目录会自动创建 `plugin_data/astrbot_plugin_bot_menu/fonts/`，可放入 `.ttf/.otf/.ttc/.woff/.woff2` 并在 Page 中按文件名或相对路径选择；详见 `docs/font-system.md`。
- 样式管理：主题预设卡片预览、复制当前样式到其他菜单、一键重置样式且不删除菜单内容、对比度检查与一键修复颜色
- 背景编辑模式：点击“编辑背景图”后才允许拖动/拉伸背景；退出后锁定背景，只能编辑卡片和分组
- 背景数字化编辑：缩放滑杆、X/Y 位置输入与拖动裁剪实时同步，支持居中、铺满、适应、重置、遮罩、模糊、亮度
- 卡片样式：支持紧凑、标准、大卡、横幅四种菜单项样式，并可在编辑器中随时切换
- 聊天指令：
  - `/menu`：发送上下文默认菜单
  - `/menu <方案ID|别名>`：发送指定菜单
  - `/menu list`：列出菜单、别名与缓存状态
  - `/menu search 关键词`：搜索菜单项
  - `/menu refresh [方案ID|别名]`：管理员刷新缓存
  - `/菜单`、`/菜单 <方案ID|别名>`：中文别名

## 安装

将本目录放入 AstrBot 的 `data/plugins/` 下，然后在 AstrBot WebUI 中启用或重载插件。

```text
AstrBot/data/plugins/astrbot_plugin_bot_menu/
```

插件本地 PNG 渲染依赖 `Pillow`、`playwright` 与 `jinja2`；AstrBot 安装插件依赖时会读取 `requirements.txt` 自动安装。

## 使用

1. 打开 AstrBot WebUI。
2. 进入插件详情页，打开 `Bot 菜单` 的 `menu-editor` 页面。
3. 编辑菜单方案并保存。
4. 在聊天中发送 `/menu` 或 `/menu default` 查看菜单图片。

## 背景与透明度

- 上传背景图不限制尺寸；新菜单优先写入本地 `assets/` 资产库并在菜单中保存资产 ID，旧菜单中的 Data URL 背景继续兼容。
- Page 编辑时先使用临时对象 URL 预览大图，保存时再转入资产库，降低大图编辑卡顿。
- 点击“编辑背景图”进入背景模式后，才能拖动背景或拖动虚线边框四角调整缩放与裁剪；再次点击会锁定背景，恢复卡片/分组点击编辑。
- “前景菜单透明度”支持 `0%` 到 `100%`，Page 预览、浏览器渲染和 Pillow 降级渲染保持一致。

## 渲染缓存

- 每次在 Page 中保存菜单后，插件会在后台自动渲染并缓存菜单图片。
- Page 会轮询只读接口 `GET /astrbot_plugin_bot_menu/menus/render-status/<menu_id>`，显示“缓存生成中 / 缓存已更新 / 缓存生成失败”。
- 聊天中发送 `/menu` 或 `/菜单` 时优先直接发送缓存图片，不再每次重复渲染。
- 再次修改并保存同一菜单后，后台会重新渲染并替换该菜单的缓存图片。
- 如果缓存还在生成中，聊天侧会提示稍后再试，避免在指令触发时阻塞重复渲染。

## 配置

插件提供 `_conf_schema.json`：

- `default_menu_id`：默认菜单方案 ID。
- `render_width`：默认渲染宽度。
- `render_scale`：图片清晰度倍率，默认 `4`，用于 Playwright/browser 截图和 Pillow 降级渲染。
- `render_mode`：菜单图片渲染模式，默认 `browser`（优先 Playwright/Chromium，失败后探测 Windows/macOS/Linux 系统浏览器），可选 `auto`、`remote` 或 `pillow`。
- `show_render_error_detail`：调试时在聊天侧显示详细渲染错误。

插件数据保存在：

```text
data/plugin_data/astrbot_plugin_bot_menu/menus.json
data/plugin_data/astrbot_plugin_bot_menu/assets.json
data/plugin_data/astrbot_plugin_bot_menu/routing.json
data/plugin_data/astrbot_plugin_bot_menu/history.json
data/plugin_data/astrbot_plugin_bot_menu/assets/
data/plugin_data/astrbot_plugin_bot_menu/fonts/
```

`menus.json`、`assets.json`、`routing.json` 使用原子写入与滚动备份；删除菜单前会自动创建历史快照。

## 渲染说明

本插件默认使用跨平台 Playwright/Chromium 进行 4x 无头高清截图（`browser` 模式），失败时会继续探测 Windows、macOS 与 Linux 上常见的 Edge、Chrome、Chromium、Brave 浏览器；该模式复用 Page 实时预览的同款 HTML 结构和 CSS 排版，并且不受 AstrBot 远程 T2I 服务波动影响。若使用 `auto`，会先尝试 browser，同款截图失败后再尝试 AstrBot 远程 T2I，最后回退到纯 Python 的 Pillow 绘制引擎。

## 更新日志

详见 [CHANGELOG.md](./CHANGELOG.md)。
