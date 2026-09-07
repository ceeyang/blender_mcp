# blender-mcp-pro（本地自研版）

让 Claude Code 通过 MCP 直接驱动本机 Blender 5.2 LTS：17 个类目、159 个工具，
覆盖场景/物体、材质、shader 与几何节点、灯光、修改器、动画、相机、渲染、导入导出、UV/烘焙、
批处理、资产（Poly Haven / Sketchfab / 本地资产库）、绑定与绑定诊断、场景工具、一键工作流。

完整工具清单见 [tools.md](tools.md)（由 `dump-tools` 生成）。设计与决策见
[superpowers/specs/2026-09-07-blender-mcp-pro-design.md](superpowers/specs/2026-09-07-blender-mcp-pro-design.md)。

## 架构

```
Claude Code ──stdio──▶ MCP server（src/blender_mcp_pro，uv 管理的 Python 3.11+）
                            │  每个工具：类型化签名 → {tool, params} JSON 转发
                            ▼
                    127.0.0.1:9877（4 字节长度前缀 + JSON 帧）
                            │
                Blender 5.2 extension（addon/blender_mcp_pro，Blender 内置 Python 3.13）
                            │  守护线程收请求 → 主线程串行执行 bpy
                            ▼
                    handlers/<类目>.py：真正的 bpy 代码
```

插件进程零联网；Poly Haven / Sketchfab 下载只发生在 server 进程，落盘到 `~/.cache/blender-mcp-pro/` 后再让插件按路径导入。

## 安装

前提：macOS，Blender 5.2 LTS 在 `/Applications/Blender.app`，已装 [uv](https://docs.astral.sh/uv/)。

```bash
cd /Users/panda/Documents/github/blender_mcp
uv sync
uv run blender-mcp-pro install-addon        # 软链 addon/ 进 ~/Library/Application Support/Blender/5.2/extensions/user_default/ 并启用
                                            # 软链加载有问题时：uv run blender-mcp-pro install-addon --copy
```

`install-addon` 会用无头 Blender 启用扩展并保存偏好。**如果此时有 GUI Blender 开着**，它退出时会用自己内存里的偏好覆盖，
所以在已打开的 Blender 里再手动确认一次：Edit ▸ Preferences ▸ Add-ons，搜 "MCP Pro"，勾上。
启用后默认自动起 server；3D 视口按 N，"MCP Pro" 页可看状态、手动 Start/Stop、改端口。

接入 Claude Code：

```bash
claude mcp add --scope user blender-pro -- uv --directory /Users/panda/Documents/github/blender_mcp run blender-mcp-pro serve
claude mcp list        # 看到 blender-pro … Connected
```

其他 MCP 客户端（Cursor 等）用同样的命令 `uv --directory <仓库> run blender-mcp-pro serve`（stdio）。

## 使用约定

- 位置/旋转/缩放都是 `[x, y, z]`，旋转是**弧度**欧拉角；颜色 `[r, g, b]` 或 `[r, g, b, a]`，0–1。
- 凡接受 `objects` 的工具：名字列表，或 `{"pattern": "Cube*"}` / `{"collection": "Props"}` / `{"type": "MESH"}` / `{"selected": true}`。
- 找不到对象/材质/节点/插槽时，错误信息会列出候选名。
- 所有写操作在 Blender 里 Ctrl+Z 可撤销（也有 `undo` / `redo` 工具，仅 GUI）。
- Principled BSDF 插槽用 5.2 的名字：`Base Color, Metallic, Roughness, IOR, Alpha, Emission Color, Emission Strength, Specular IOR Level, …`
- `execute_code` 是兜底：任意 Python，预置 `bpy / bmesh / mathutils / Vector / math`。
- `get_api_docs("bpy.types.Object.location")` 本地查 bpy 文档，不联网。

## 开发与测试

```bash
uv run pytest -q                            # 149 个用例；集成测试自动拉起无头 Blender（约 2 s）
BLENDER_MCP_ONLINE_TESTS=1 uv run pytest tests/test_assets.py   # 顺带跑 Poly Haven 联网用例
uv run blender-mcp-pro dump-tools > docs/tools.md               # 工具清单
```

- 改了插件代码：Blender 里 F3 → "Reload Scripts"（软链安装下源码即生效）。
- 改了 server 代码：Claude Code 里重启该 MCP（`/mcp`）。
- 新增工具：`handlers/<类目>.py` 里 `@command("name")` + `tools/<类目>.py` 里 `@mcp.tool()`，`tests/test_parity.py` 会盯住两边名字一致。
- handler 模块**顶层不能调用 bpy**（对账测试用假 bpy 加载插件）；只在函数体里用。

## 已知限制

- `viewport_screenshot`、`undo`/`redo` 需要 GUI Blender；无头模式明确报错。
- 无头模式下 EEVEE 能否渲染取决于 GPU 上下文；测试固定用 WORKBENCH。GUI 里 EEVEE/Cycles 都正常。
- Sketchfab 下载要 API token：Preferences ▸ Add-ons ▸ Blender MCP Pro 里填，或环境变量 `SKETCHFAB_API_TOKEN`。
- 只做 5.2 LTS，不兼容 4.x。
