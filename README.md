# blender_mcp — blender-mcp-pro 本地自研版

让 Claude Code（或任何 MCP 客户端）驱动本机 Blender 5.2 LTS：17 类 159 个工具。

- 安装、接入 Claude Code、开发与测试：**[docs/README.md](docs/README.md)**
- 全部工具清单：[docs/tools.md](docs/tools.md)
- 设计与决策：[docs/superpowers/specs/2026-09-07-blender-mcp-pro-design.md](docs/superpowers/specs/2026-09-07-blender-mcp-pro-design.md)

```bash
uv sync
uv run blender-mcp-pro install-addon
claude mcp add --scope user blender-pro -- uv --directory <仓库绝对路径> run blender-mcp-pro serve
```
