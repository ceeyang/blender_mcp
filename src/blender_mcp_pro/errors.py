class BlenderError(Exception):
    """Blender 插件侧 handler 抛出的异常，带类型与 traceback。"""

    def __init__(self, type_: str, message: str, traceback: str = ""):
        self.type = type_
        self.message = message
        self.traceback = traceback
        super().__init__(f"{type_}: {message}")


class BlenderUnavailable(Exception):
    """连不上插件 server。"""


class BlenderTimeout(Exception):
    """插件在超时时间内没回结果。"""
