# PITFALLS — blender-mcp-pro

## [2026-09-07] 无头 Blender 里 bpy.app.timers 不会触发
症状：`blender -b --python` 起的 TCP server 收到请求后永远不回。
根因：background 模式没有窗口事件循环，timers 不跑（实测 `timers.register` 后 sleep 0.5s 回调未触发）。
规则：无头启动脚本自己在主线程 `while: drain_once(); sleep(0.003)`；GUI 才用 timer。
涉及：addon/blender_mcp_pro/server.py, tests/addon_boot.py

## [2026-09-07] Blender 5.2 几何节点修改器输入不再是 mod["Socket_N"]
症状：`mod["Socket_2"] = 4.0` 报 `id properties not supported for this type`；改用 `mod.properties.inputs["Socket_2"] = 4.0` 不报错但修改器不生效。
根因：5.x 把输入挂到 `mod.properties.inputs.<identifier>`（RNA struct，含 `.value/.attribute_name/.type`）；`ins[id] = v` 会把整组结构覆盖成裸值。
规则：`getattr(mod.properties.inputs, identifier).value = v`；接口新增插槽后先重新赋一次 `mod.node_group` 触发同步。
涉及：addon/blender_mcp_pro/handlers/geometry_nodes.py

## [2026-09-07] path_resolve 只认双引号
症状：`obj.path_resolve("modifiers['Bevel']")` → could not be resolved。
根因：Blender RNA 路径语法固定用 `["name"]`。
规则：进 `path_resolve` 前把 `['` `']` 换成 `["` `"]`（`handlers/animation.py::_set_path`）。

## [2026-09-07] background 模式没有 undo 栈
症状：`bpy.ops.ed.undo()` poll 失败 "context is incorrect"。
规则：`undo/redo` 工具在 `bpy.app.background` 下直接 ToolError；只在 GUI 验证。`undo_push` 本身在无头下不报错。

## [2026-09-07] 不能从当前打开的 .blend 追加数据
症状：`bpy.data.libraries.load(bpy.data.filepath)` → "Cannot load from the current blend file"。
规则：`append_from_blend` 先比对路径并报清楚；测试要先 `save_blend` 到另一个文件再追加。

## [2026-09-07] mcp 2.x 改名：FastMCP → MCPServer
症状：`from mcp.server.fastmcp import FastMCP` 抛 ModuleNotFoundError（uv 解析到 mcp 2.x）。
规则：`from mcp.server.mcpserver import MCPServer, Image`；`.tool()/.run("stdio")/.list_tools()` 用法不变；`Tool.inputSchema` 仍是驼峰。

## [2026-09-07] 对账测试用假 bpy 加载插件，handler 顶层不能碰 bpy
症状：某 handler 模块顶层写了 `bpy.types.X.bl_rna...` 常量，`test_parity` 直接 AttributeError。
规则：枚举/RNA 表一律放函数里并做模块级缓存（见 modifiers.py `_TYPES_CACHE`、nodes_common.py `_base_props()`）。

## [2026-09-07] mcp 2.x 把普通异常吞成 "Error executing tool <name>"
症状：stdio 端到端里 `get_object_info("Nope")` 回给模型的只有 "Error executing tool get_object_info"，候选名提示全丢。
根因：`MCPServer` 只把 `mcp.server.mcpserver.exceptions.ToolError` 的消息放进 `content`（`is_error=True`），其它异常按 crash 处理、只记日志。
规则：server 侧工具的所有异常都要转成 `ToolError`——`tools/_base.py::call` 统一包了 Blender 侧错误，不走 `call()` 的工具用 `@surface_errors`。
涉及：src/blender_mcp_pro/tools/_base.py, tools/assets.py, tests/test_mcp_stdio.py

## [2026-09-07] Windows 上 socket 发完立刻 close 会让对端丢响应
症状：`tests/test_protocol.py` 的假 Blender 间歇失败（约 8%）：客户端第一次读到 `ConnectionResetError [WinError 10054]`，重连后无人 accept，等满 60s 超时。
根因：Windows TCP 栈在 `sendall()` 后立即 `close()` 有概率发 RST 而不是 FIN，对端收到 RST 时丢弃已缓冲的数据。
规则：服务端回完响应不要立刻关；假服务器 `recv()` 到客户端 EOF 再关（真实插件本来就是长连接）。
涉及：tests/test_protocol.py

## [2026-09-07] Python 3.12 的 Path.is_symlink() 对 Windows junction 返回 False
症状：`install-addon` 第二次运行时旧安装是 junction，原代码走进 `shutil.rmtree` 分支。
根因：3.12 起 `os.path.islink` 不再把 junction 当链接，要用 `os.path.isjunction`；rmtree 会拒绝 reparse point（更老版本可能顺着删源码）。
规则：删安装目录统一走 `cli._remove()`：symlink / junction / 文件用 `unlink()`，只有真实目录才 `rmtree`。
涉及：src/blender_mcp_pro/cli.py
