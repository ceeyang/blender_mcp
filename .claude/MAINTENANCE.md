# MAINTENANCE — blender-mcp-pro 本地自研版

更新：2026-09-08

## 项目快照

- 让 Claude Code 通过 MCP 驱动本机 Blender 5.2 LTS，复刻 blender-mcp-pro 的 17 类 159 个工具。
- Python 3.11+（uv）MCP server（`mcp` 2.x，`MCPServer`）+ Blender extension（内置 Python 3.13），TCP 127.0.0.1:9877。
- 纯本地部署：`uv run blender-mcp-pro install-addon` + `claude mcp add … serve`。文档在 `docs/`。

## 架构约束（代码里读不出来的）

- **插件进程零联网**。联网只允许在 `src/blender_mcp_pro/assets/`；下载落盘后让插件按路径导入。
- **handler 模块顶层不得调用 bpy**：`tests/test_parity.py` 用假 bpy 加载整个插件包来读 `HANDLERS`，顶层一碰 bpy 就炸。
- **无头模式 `bpy.app.timers` 不触发**：GUI 用 timer 驱动 `server.drain_once()`，`tests/addon_boot.py` 自己在主线程循环。
- 工具名两边各出现一次（`tools/<类目>.py` 与 `handlers/<类目>.py`），由对账测试锁住；`SERVER_ONLY` 集合是唯一例外。
- 内部命令 `ping / reset_scene / shutdown / get_secret` 用 `internal=True`，不暴露为 MCP 工具。
- 所有 mutating handler 执行后由 `registry.dispatch` 统一 `undo_push`；只读工具必须标 `mutates=False`，否则会污染 undo 栈。
- 同一 handler 里改完 `location` 立刻读 `matrix_world` 是旧值，先 `utils.refresh()`。
- 返回值必须过 `serialize()`（float 会 round 到 6 位，否则 float32 精度在断言里对不上）。
- `obj_brief` 的 `dimensions` 不能读 `o.dimensions`（depsgraph 缓存，刚改完 scale 是旧值），
  用 `utils.dimensions_of()` 手算 bbox×scale。
- 每个工具必须声明 `annotations`（`tools/_types.py` 的 READ_ONLY/CREATE/UPDATE/DESTRUCTIVE/
  WRITES_FILE/NET_READ/NET_WRITE 预设）且每个参数带 `Field(description=...)`，
  由 `tests/test_tool_definitions.py` 强制；描述用英文。

## 关键决策

- 2026-09-08 按 Glama 的 TDQS 重写全部 159 个工具定义：补 annotations、参数描述、
  兄弟工具选型指引，描述改英文。动机不是分数，是实测发现模型会因参数语义不明填错值
  （`relative` 默认值两个工具相反、`randomize_transform` 的 scale 基准是 1 不是 0）。

见 `docs/superpowers/specs/2026-09-07-blender-mcp-pro-design.md` §9（胖 addon + 薄 server、只做 5.2、长度前缀帧、
资产下载在 server 进程、节点工具按 material / node_group 分两套名字）。补充一条：
- 2026-09-07 用 mcp 2.x（uv 解析到的最新版）而不是 pin `mcp<2`：API 只差 `FastMCP→MCPServer` 一个名字，没理由锁旧版。

## 进行中与待办

- [x] GUI 端到端：2026-09-07 在 Windows GUI Blender 里验证了 `viewport_screenshot` / `render_image` / `frame_objects` / `save_blend`；`undo` 仍待验。
- [ ] Sketchfab 下载未真实联网实测（需要 token）；调用链已由 `tests/test_assets_download.py` mock 覆盖。
      Poly Haven 联网用例用 `BLENDER_MCP_ONLINE_TESTS=1` 跑。
- [ ] 159 个工具 schema 占上下文不小；若 Claude Code 侧感觉慢，考虑给 server 加「类目开关」环境变量。

## 数据与部署注意

- extensions 目录用软链：`~/Library/Application Support/Blender/5.2/extensions/user_default/blender_mcp_pro → addon/blender_mcp_pro`。
  改源码后 Blender 里 Reload Scripts 即生效。
- Windows（2026-09-07 实测 Win11 + Blender 5.2.1）：扩展目录在 `%APPDATA%/Blender Foundation/Blender/5.2/extensions/user_default`；
  普通用户建软链报 WinError 1314，`install-addon` 自动退到目录 junction（`_winapi.CreateJunction`），效果同软链。
  全套 153 个用例在 Windows 无头 Blender 上通过。
- `install-addon` 走无头 Blender `save_userpref()`；GUI 开着时退出会覆盖偏好，需在 GUI 里再启用一次。
- 渲染/下载缓存在 `~/.cache/blender-mcp-pro/`（`renders/`、`hdris/`、`textures/`、`models/`、`sketchfab/`），可随时清。
- 测试产物在项目 `tmp/`（gitignore）；无头 Blender 日志 `tmp/blender_test.log`。
