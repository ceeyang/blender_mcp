from mcp.server.mcpserver import MCPServer

mcp = MCPServer(
    "blender-mcp-pro",
    instructions=(
        "本地 Blender 5.2 控制器。位置/旋转/缩放为 [x,y,z]，旋转用弧度；颜色 0–1。"
        "先 get_scene_info 了解场景再操作；对象找不到时错误信息会列出候选名。"
        "写操作可在 Blender 里 Ctrl+Z 撤销，也可用 undo 工具。"
        "凡接受 objects 的工具：名字列表，或 {pattern}/{collection}/{type}/{selected:true} 之一。"
    ),
)


def main():
    from . import tools  # noqa: F401  注册全部工具
    mcp.run(transport="stdio")
