"""Blender MCP Pro (local) — extension entry."""
import bpy

ADDON_VERSION = "0.1.0"


class Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    host: bpy.props.StringProperty(name="Host", default="127.0.0.1")
    port: bpy.props.IntProperty(name="Port", default=9877, min=1024, max=65535)
    autostart: bpy.props.BoolProperty(name="Auto start server", default=True)
    sketchfab_token: bpy.props.StringProperty(name="Sketchfab API token", default="", subtype="PASSWORD")

    def draw(self, context):
        from . import server
        col = self.layout.column()
        col.prop(self, "host")
        col.prop(self, "port")
        col.prop(self, "autostart")
        col.prop(self, "sketchfab_token")
        st = server.status()
        if st["running"]:
            col.label(text=f"Status: running on {st['host']}:{st['port']}", icon="CHECKMARK")
            col.operator("mcp_pro.stop_server", icon="PAUSE")
        else:
            col.label(text="Status: stopped", icon="X")
            col.operator("mcp_pro.start_server", icon="PLAY")


class MCP_OT_start(bpy.types.Operator):
    bl_idname = "mcp_pro.start_server"
    bl_label = "Start MCP server"

    def execute(self, context):
        from . import server
        p = context.preferences.addons[__package__].preferences
        server.start(p.host, p.port)
        return {"FINISHED"}


class MCP_OT_stop(bpy.types.Operator):
    bl_idname = "mcp_pro.stop_server"
    bl_label = "Stop MCP server"

    def execute(self, context):
        from . import server
        server.stop()
        return {"FINISHED"}


class VIEW3D_PT_mcp_pro(bpy.types.Panel):
    bl_label = "MCP Pro"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MCP Pro"

    def draw(self, context):
        from . import server
        st = server.status()
        col = self.layout.column()
        if st["running"]:
            col.label(text=f"Running {st['host']}:{st['port']}", icon="CHECKMARK")
            col.label(text=f"handled {st['handled']} · {st['uptime']}s")
            col.operator("mcp_pro.stop_server", icon="PAUSE")
        else:
            col.label(text="Stopped", icon="X")
            col.operator("mcp_pro.start_server", icon="PLAY")


_classes = (Preferences, MCP_OT_start, MCP_OT_stop, VIEW3D_PT_mcp_pro)


def register():
    for c in _classes:
        bpy.utils.register_class(c)
    from . import handlers  # noqa: F401
    from . import server
    server.autostart_if_configured()


def unregister():
    from . import server
    server.stop()
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
