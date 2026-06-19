# AstrBot Bot 菜单插件

一个用于自定义机器人菜单的 AstrBot 插件：在 WebUI 中编辑多套菜单方案，实时预览，并通过聊天指令发送渲染后的菜单图片。

## 功能

- 插件 Pages 页面：`menu-editor`
- 多菜单方案：支持新建、复制、删除、导入、导出
- 可视化编辑：标题、副标题、分组、菜单项、图标、指令、描述、启用状态，支持分组和菜单项复制、上移、下移
- 样式配置：主题预设、主色、背景色、自定义背景图（不限上传尺寸）、前景菜单透明度（0%-100%）、卡片色、文字色、辅助文字色、智能/手动宽度、每行卡片数、圆角、更新时间
- 背景裁剪：在 Page 实时预览中拖动背景，或拖动边框控制背景缩放与裁剪位置
- 卡片模板：支持紧凑、标准、大卡、横幅四种菜单项模板，并可在编辑器中随时切换
- 聊天指令：
  - `/menu`：发送默认菜单
  - `/menu <方案ID>`：发送指定菜单
  - `/菜单`、`/菜单 <方案ID>`：中文别名

## 安装

将本目录放入 AstrBot 的 `data/plugins/` 下，然后在 AstrBot WebUI 中启用或重载插件。

```text
AstrBot/data/plugins/astrbot_plugin_bot_menu/
```

插件本地 PNG 渲染依赖 `Pillow`，AstrBot 安装插件依赖时会读取 `requirements.txt` 自动安装。

## 使用

1. 打开 AstrBot WebUI。
2. 进入插件详情页，打开 `Bot 菜单` 的 `menu-editor` 页面。
3. 编辑菜单方案并保存。
4. 在聊天中发送 `/menu` 或 `/menu default` 查看菜单图片。

## 配置

插件提供 `_conf_schema.json`：

- `default_menu_id`：默认菜单方案 ID。
- `render_width`：默认渲染宽度。
- `render_scale`：图片清晰度倍率，默认 `4`，用于 browser 截图和 Pillow 降级渲染。
- `render_mode`：菜单图片渲染模式，默认 `browser`（调用系统 Edge/Chrome），可选 `auto`、`remote` 或 `pillow`。
- `show_render_error_detail`：调试时在聊天侧显示详细渲染错误。

菜单正文数据保存在：

```text
data/plugin_data/astrbot_plugin_bot_menu/menus.json
```

## 说明

本插件默认调用 Windows 系统内置的 Edge 浏览器或 Chrome 进行 4x 无头高清截图（`browser` 模式），复用 Page 实时预览的同款 HTML 结构和 CSS 排版，并且不受 AstrBot 远程 T2I 服务波动影响。Page 中的智能宽度会按标题、描述、卡片模板和每行卡片数自动计算图片宽度，避免少量内容渲染出过宽图片；需要固定尺寸时也可以切换为手动宽度。若使用 `auto`，会先尝试 browser，同款截图失败后再尝试 AstrBot 远程 T2I，最后回退到纯 Python 的 Pillow 绘制引擎。插件 Web API 兼容带 `astrbot.api.web` 的新版 AstrBot，以及仍使用 Quart 插件路由的 AstrBot 4.25.x。
