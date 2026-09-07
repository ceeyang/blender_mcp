# MAINTENANCE — blender-mcp-pro 本地自研版

更新：2026-09-07

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

## 关键决策

见 `docs/superpowers/specs/2026-09-07-blender-mcp-pro-design.md` §9（胖 addon + 薄 server、只做 5.2、长度前缀帧、
资产下载在 server 进程、节点工具按 material / node_group 分两套名字）。补充一条：
- 2026-09-07 用 mcp 2.x（uv 解析到的最新版）而不是 pin `mcp<2`：API 只差 `FastMCP→MCPServer` 一个名字，没理由锁旧版。

## 进行中与待办

- [ ] GUI 端到端：插件已装进 extensions 目录，需在已打开的 Blender 里启用后跑 `viewport_screenshot` / `undo` 验证。
- [ ] Sketchfab 下载未实测（需要 token）。Poly Haven 联网用例用 `BLENDER_MCP_ONLINE_TESTS=1` 跑。
- [ ] 159 个工具 schema 占上下文不小；若 Claude Code 侧感觉慢，考虑给 server 加「类目开关」环境变量。

## 数据与部署注意

- extensions 目录用软链：`~/Library/Application Support/Blender/5.2/extensions/user_default/blender_mcp_pro → addon/blender_mcp_pro`。
  改源码后 Blender 里 Reload Scripts 即生效。
- `install-addon` 走无头 Blender `save_userpref()`；GUI 开着时退出会覆盖偏好，需在 GUI 里再启用一次。
- 渲染/下载缓存在 `~/.cache/blender-mcp-pro/`（`renders/`、`hdris/`、`textures/`、`models/`、`sketchfab/`），可随时清。
- 测试产物在项目 `tmp/`（gitignore）；无头 Blender 日志 `tmp/blender_test.log`。
