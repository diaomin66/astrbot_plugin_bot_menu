# AstrBot Bot 菜单插件


一个用于自定义机器人菜单的 AstrBot 插件：在 WebUI 中编辑多套菜单方案，实时预览，并通过聊天指令发送渲染后的菜单图片。

- 当前版本：`0.3.0`
- 作者：雪碧bir
- 交流与反馈：**[点击加入 QQ 群 1081773675](https://qm.qq.com/q/Qr45Vz0a8o)**

## 效果图

<img width="1280" height="1068" alt="c029cb7bdef068975a557a60a2644e8a_720" src="https://github.com/user-attachments/assets/67f9865b-3327-448b-88f6-26958f5c14c6" />


## 功能

- 插件 Pages 页面：`menu-editor`
- 多菜单方案：支持新建、复制、删除、导入、导出
- 可视化编辑：标题、副标题、分组、菜单项、图标、指令、描述、启用状态，支持分组和菜单项复制、上移、下移
- 编辑安心体验：未保存状态提示、离开/切换菜单确认、本地草稿自动保存与恢复/丢弃提示
- 大菜单编辑：前端即时校验、保存前滚动到首个错误、分组/菜单项折叠状态记忆、菜单项搜索过滤
- 样式配置：主题预设、主色、背景色、自定义背景图（不限上传尺寸）、前景菜单透明度（0%-100%）、卡片色、文字色、辅助文字色、智能/手动宽度、每行卡片数、智能/自定义分组间距（0-200，0 为完全贴合）、圆角、更新时间
- 样式管理：主题预设卡片预览、复制当前样式到其他菜单、一键重置样式且不删除菜单内容
- 背景裁剪：在 Page 实时预览中拖动背景，或拖动边框控制背景缩放与裁剪位置
- 背景数字化编辑：缩放滑杆、X/Y 位置输入与拖动裁剪实时同步，支持居中、铺满、重置背景
- 卡片样式：支持紧凑、标准、大卡、横幅四种菜单项样式，并可在编辑器中随时切换
- 聊天指令：
  - `/menu`：发送默认菜单
  - `/menu <方案ID>`：发送指定菜单
  - `/菜单`、`/菜单 <方案ID>`：中文别名

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

- 上传背景图不限制尺寸，编辑器会把图片保存为菜单配置中的 Data URL。
- 在 Page 预览卡片中直接拖动背景可调整位置。
- 拖动背景虚线边框的四角可调整缩放与裁剪区域。
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

菜单正文数据保存在：

```text
data/plugin_data/astrbot_plugin_bot_menu/menus.json
```

## 渲染说明

本插件默认使用跨平台 Playwright/Chromium 进行 4x 无头高清截图（`browser` 模式），失败时会继续探测 Windows、macOS 与 Linux 上常见的 Edge、Chrome、Chromium、Brave 浏览器；该模式复用 Page 实时预览的同款 HTML 结构和 CSS 排版，并且不受 AstrBot 远程 T2I 服务波动影响。若使用 `auto`，会先尝试 browser，同款截图失败后再尝试 AstrBot 远程 T2I，最后回退到纯 Python 的 Pillow 绘制引擎。

## 更新日志

详见 [CHANGELOG.md](./CHANGELOG.md)。
