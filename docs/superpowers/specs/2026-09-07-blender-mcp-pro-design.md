# blender-mcp-pro（本地自研版）设计

> 状态：已批准（2026-09-07）。实施计划见 `docs/superpowers/plans/`。
> 目标：在本机复刻 blender-mcp-pro 的功能面（17 类、159 个工具），
> 供 Claude Code 通过 MCP 直接驱动本地 Blender 5.2 LTS。

## 1. 目标与边界

**做什么**

- 一个 Blender 5.2 extension（插件）+ 一个 Python MCP server，二者通过 `localhost` TCP 通信。
- 覆盖 blender-mcp-pro 公布的 17 个类目：场景/物体、材质、shader 节点、灯光、修改器、动画、
  几何节点、相机、渲染、导入导出、UV 与贴图、批处理、资产、绑定、绑定诊断、场景工具、工作流。
- 通过 stdio 接入 Claude Code；其他 MCP 客户端（Cursor 等）天然可用，但不做专门适配。

**不做什么**

- 不兼容 Blender 4.x。只按 5.2 LTS 的 API 写（Principled BSDF 插槽名、extension manifest、
  `bpy.app.timers` 等），不写版本分支。
- 不做 Streamable HTTP 传输。stdio 够用；要加也只是 FastMCP 一行配置，不进本期。
- 不复制 blender-mcp-pro 的代码。只以其功能清单为规格，全部自行实现。
- 不做 GUI 之外的视口能力兜底：`viewport_screenshot` 等需要 3D 视图的工具在无头模式下明确报错，不模拟。

**联网边界**：插件进程零联网。唯一联网的是 server 进程里的资产下载（Poly Haven / Sketchfab），
下载完落盘到 `~/.cache/blender-mcp-pro/`，再让插件按本地路径导入。

## 2. 架构

采用「胖 addon + 薄 server」：

```
Claude Code ──stdio──▶ MCP server (FastMCP, uv 管理的 Python 3.11)
                            │  tools/<类目>.py：类型化签名 → {tool, params} JSON
                            │  connection.py：TCP 客户端，长度前缀帧，超时/重连
                            ▼
                    localhost:9877 (TCP)
                            │
                Blender 5.2 extension (Python 3.13，Blender 内置)
                            │  server.py：守护线程 accept → 请求入队
                            │  bpy.app.timers 回调在主线程逐个执行 handler
                            ▼
                    handlers/<类目>.py：真正的 bpy 代码
```

**为什么这样分**：bpy 不是线程安全的，所有 bpy 调用必须在 Blender 主线程；把逻辑放插件侧，
就能用 `blender -b` 无头跑真实集成测试，错误也是真实 traceback。server 侧不依赖 Blender，
可以独立单测、秒起。代价是工具名两边各出现一次，用对账测试（§7）锁住。

### 2.1 仓库布局

```
pyproject.toml                       uv 项目；name = blender-mcp-pro；requires-python >= 3.11
                                     依赖：mcp[cli]、httpx（仅资产下载）；dev：pytest
src/blender_mcp_pro/
  __init__.py
  server.py                          创建 FastMCP("blender-mcp-pro")，import tools.* 完成注册，stdio 运行
  connection.py                      BlenderConnection：connect/send/close；长度前缀 JSON；超时；断线重连一次
  errors.py                          BlenderError（携带 type/message/traceback），转成 MCP 工具错误文本
  tools/
    __init__.py                      导入所有类目模块，导出 ALL_TOOL_NAMES（供对账测试）
    scene.py materials.py shader_nodes.py lights.py modifiers.py animation.py
    geometry_nodes.py camera.py render.py io.py uv_texture.py batch.py
    assets.py rigging.py rig_diagnostics.py utilities.py workflows.py
  assets/
    polyhaven.py                     Poly Haven 公开 API：分类/搜索/下载 + 本地缓存
    sketchfab.py                     Sketchfab API：搜索/下载（需 API token）
    cache.py                         ~/.cache/blender-mcp-pro/ 目录管理
  cli.py                             `blender-mcp-pro serve` / `install-addon` / `uninstall-addon`
addon/blender_mcp_pro/
  blender_manifest.toml              id = blender_mcp_pro；blender_version_min = "5.2.0"
  __init__.py                        register/unregister；AddonPreferences（host/port/autostart/sketchfab_token）；N 面板
  server.py                          BlenderTCPServer：监听线程、请求队列、timers 主线程分发
  registry.py                        @command("tool_name", internal=False) 装饰器 → HANDLERS；internal=True 的（ping/reset_scene/shutdown/get_secret）不暴露为 MCP 工具
  protocol.py                        帧编解码（与 src/.../connection.py 镜像，无共享依赖）
  utils.py                           find_object/find_material 等查找 + "not found 附候选名"；向量/颜色序列化；mode 上下文管理器；undo_push
  nodes_common.py                    shader 与 geometry 共用的节点树操作（add/remove/link/set input/dump/build）
  handlers/
    __init__.py                      import 全部类目，触发注册
    <与 tools/ 同名的 17 个文件>
tests/
  conftest.py                        blender_server fixture：拉起无头 Blender + 插件，等端口就绪；session 级
  addon_boot.py                      在 Blender 内执行：从源码目录 import 插件、注册、起测试端口、保活循环
  test_parity.py                     ALL_TOOL_NAMES == {name for name, h in HANDLERS.items() if not h.internal}
  test_connection.py                 帧编解码、超时、错误映射（假 socket）
  test_<类目>.py                     走真实 socket 打到无头 Blender
docs/
  README.md                          安装、接入 Claude Code、开发/测试方式
  tools.md                           工具清单（从 server 注册表生成，不手写）
tmp/                                 gitignore
```

### 2.2 进程与线程模型（插件侧）

- `register()` 时若偏好里 `autostart` 为真则起 server；N 面板提供 Start/Stop 按钮和状态行。
- 监听线程只做 accept + 读帧 + 写帧；每条请求封装成 `(request, threading.Event, result_holder)` 放入 `queue.Queue`。
- `bpy.app.timers.register(_drain, persistent=True)`，每 0.05s 触发一次，取空队列：逐条执行 handler，写结果，`event.set()`。
  一次 drain 最多处理 N 条（默认 20）以免长时间占主线程。
- 同一时刻只处理一个请求（队列天然串行）。渲染、烘焙这类长任务会占住主线程直到完成，这是 Blender 的正常行为。
- `unregister()` 关闭监听 socket、停 timer、清队列（待处理请求全部返回 `ServerStopped` 错误）。

## 3. 通信协议

- 地址：`127.0.0.1:9877`（偏好可改；server 侧对应 `BLENDER_MCP_HOST/PORT` 环境变量或 CLI 参数）。
- 帧：4 字节大端无符号长度 + UTF-8 JSON。单帧上限 64 MiB（够放 base64 渲染图）。
- 请求：`{"id": "<uuid4>", "tool": "<name>", "params": {...}}`
- 成功：`{"id": "...", "ok": true, "result": <JSON>}`
- 失败：`{"id": "...", "ok": false, "error": {"type": "KeyError", "message": "...", "traceback": "..."}}`
- 内部命令（`internal=True`，不作为 MCP 工具暴露）：`ping` → `{"blender": "5.2.1", "addon": "0.1.0"}` 用于健康检查与测试就绪；`reset_scene` 回到出厂默认场景（测试隔离）；`shutdown` 让插件关掉 server（测试收尾）；`get_secret(key)` 读偏好里的密钥。
- 超时：server 侧默认 60 s；`render_image`、`render_animation`、`bake_texture`、`bake_animation`、
  `generate_rigify_rig`、`polyhaven_download`、`sketchfab_download` 为 600 s。超时后 server 关闭连接并报错，
  插件侧该请求执行完后结果丢弃。
- 二进制：图片以 `{"image_base64": "...", "mime": "image/png"}` 返回，server 转成 MCP `Image`。
  `return_image=false` 时只返回文件路径。
- 连接生命周期：server 懒连接，首次工具调用时连；断开则下一次调用重连一次，仍失败则报
  "Blender 未运行或插件未启动 server（Edit ▸ Preferences ▸ Add-ons ▸ Blender MCP Pro）"。

## 4. 通用约定（handler 侧）

- **查找**：对象/材质/节点组/相机/灯光/骨架按名字查；找不到时报错并附带同类型的最多 10 个候选名。
- **序列化**：`Vector`/`Euler`/`Color` → list；`Matrix` → 嵌套 list；枚举 → 字符串；
  数据块 → `{"name", "type"}` 简要引用。所有返回值必须可 `json.dumps`。
- **写操作**：完成后 `bpy.ops.ed.undo_push(message="mcp: <tool>")`。只读工具不推。
- **模式切换**：需要 EDIT/POSE 模式的 handler 用 `utils.mode(obj, 'EDIT')` 上下文管理器，退出时恢复原模式与原选择。
- **上下文覆盖**：需要 `bpy.ops` 且依赖区域的操作用 `bpy.context.temp_override(...)`；无头模式下没有 3D 视图区域的操作
  （视口截图、camera_to_view）直接报 `NoViewportError`，不降级。
- **数值参数**：位置/旋转/缩放统一 `[x, y, z]`，旋转为弧度制欧拉角；颜色 `[r, g, b]` 或 `[r, g, b, a]`（0–1）。
  工具描述里写明单位。
- **批量参数**：凡接受 `objects` 的工具都接受 `list[str]` 名字列表，或 `{"pattern": "Cube*"}`、
  `{"collection": "..."}`、`{"type": "MESH"}`、`{"selected": true}` 四种过滤器之一。解析逻辑集中在 `utils.resolve_objects`。
- **返回**：写操作返回被影响对象的简要信息（名字 + 关键属性），不回传整个场景。
- **5.2 API 注意**：`Material.use_nodes` 已标记 6.0 移除（5.2 会打 DeprecationWarning）。新建材质后直接用 `material.node_tree`，实现时先在无头 Blender 里确认新材质是否自带节点树，不带再兜底调用一次 `use_nodes = True`。

## 5. 工具清单

工具名两侧一致；参数只列关键项，`?` 表示可选。完整 schema 以 server 侧函数签名为准并生成到 `docs/tools.md`。

### 5.1 Scene & Objects（16）

| 工具 | 关键参数 | 说明 |
|---|---|---|
| get_scene_info | — | 场景名、帧范围、fps、单位、活动物体、集合树、各类型物体计数 |
| list_objects | type?, collection?, pattern?, selected? | 名字/类型/位置/集合/可见性 |
| get_object_info | name | 变换、尺寸、父子、集合、修改器、材质槽、顶点/面数、自定义属性 |
| create_primitive | type, name?, location?, rotation?, scale?, size?, radius?, depth?, segments?, text? | type ∈ cube/uv_sphere/ico_sphere/cylinder/cone/torus/plane/circle/monkey/empty/text |
| delete_object | objects, delete_children? | |
| duplicate_object | name, new_name?, linked?, offset? | |
| set_transform | name, location?, rotation?, scale?, relative? | |
| rename_object | name, new_name, rename_data? | |
| set_parent | child, parent?, keep_transform? | parent 为空即清除父子 |
| set_visibility | objects, hide_viewport?, hide_render?, hide_select? | |
| select_objects | objects, mode(replace/add/remove), active? | |
| manage_collection | action(create/delete/move/link/unlink/rename), name, parent?, objects?, new_name? | |
| join_objects | objects, target? | |
| apply_transforms | objects, location?, rotation?, scale? | 默认三者都应用 |
| set_origin | name, type(GEOMETRY/CURSOR/CENTER_OF_MASS/CENTER_OF_VOLUME/BOUNDS_MIN) | |
| set_custom_property | name, key, value | value 支持数字/字符串/列表；`null` 删除 |

### 5.2 Materials（9）

| 工具 | 关键参数 |
|---|---|
| list_materials | used_only? |
| get_material_info | name → 用户数、Principled 主要值、节点数、贴图路径 |
| create_material | name, base_color?, metallic?, roughness?, emission_color?, emission_strength?, alpha?, ior?, assign_to? |
| assign_material | object, material, slot?(默认 0，不存在则新建槽) |
| set_principled_inputs | material, inputs: {插槽名: 值}，插槽名用 5.2 名称（如 "Specular IOR Level"、"Emission Color"）；名字不对时报错并列出全部插槽 |
| set_material_settings | material, blend_method?, shadow_method?, backface_culling?, displacement_method?, pass_index? |
| add_image_texture | material, image_path, target("Base Color"/"Roughness"/"Metallic"/"Normal"/"Alpha"/"Emission Color"), colorspace?, projection?；Normal 自动插 Normal Map 节点 |
| create_pbr_material | name, base_color?, roughness?, metallic?, normal?, height?, ao?（各为路径）, assign_to? |
| delete_material | name, unlink_only? |

### 5.3 Shader Nodes（10）

| 工具 | 关键参数 |
|---|---|
| list_shader_nodes | material → 节点（type/name/label/location/inputs 当前值）+ 连线 |
| add_shader_node | material, type(如 ShaderNodeTexNoise), name?, location?, inputs?, properties? |
| remove_shader_node | material, node |
| set_node_input | material, node, socket, value |
| set_node_property | material, node, property, value（如 blend_type、operation、image） |
| link_nodes | material, from_node, from_socket, to_node, to_socket |
| unlink_nodes | material, to_node, to_socket |
| set_color_ramp | material, node, stops: [{position, color}], interpolation? |
| build_node_tree | material, nodes: [...], links: [...], clear?：一次性建整棵树 |
| get_node_types | tree(shader/geometry), filter? → 类型名、标签、输入/输出插槽（运行时从 bpy.types 枚举，不硬编码） |

### 5.4 Lights（6）

| 工具 | 关键参数 |
|---|---|
| list_lights | — |
| get_light_info | name |
| create_light | type(POINT/SUN/SPOT/AREA), name?, location?, rotation?, energy?, color?, radius?, size?, spot_size?, spot_blend?, target? |
| set_light | name, energy?, color?, radius?, size?, shape?, spot_size?, spot_blend?, use_shadow?, angle?(SUN) |
| point_light_at | light, target(对象名或坐标), use_constraint? |
| set_world_lighting | color?, strength?, hdri_path?, rotation? ：hdri 走 Environment Texture + Mapping |

### 5.5 Modifiers（8）

| 工具 | 关键参数 |
|---|---|
| list_modifier_types | filter? → 全部 83 种及其可设置属性名/类型/枚举 |
| list_modifiers | object |
| get_modifier_settings | object, modifier → 当前值 + 可设属性表 |
| add_modifier | object, type, name?, settings?：settings 键按 RNA 校验，未知键报错并列出可用键；对象引用型属性（如 Boolean.object）接受对象名 |
| set_modifier | object, modifier, settings |
| remove_modifier | object, modifier |
| apply_modifier | object, modifier |
| move_modifier | object, modifier, index? / direction?(UP/DOWN/TOP/BOTTOM) |

集成测试至少覆盖：SUBSURF、BEVEL、ARRAY、MIRROR、SOLIDIFY、BOOLEAN、DISPLACE、DECIMATE、SHRINKWRAP、NODES、ARMATURE、WIREFRAME、SCREW、TRIANGULATE、WELD、REMESH、SKIN、CURVE、LATTICE、SIMPLE_DEFORM、CAST、SMOOTH（22 种）。

### 5.6 Animation（15）

| 工具 | 关键参数 |
|---|---|
| get_animation_info | object? → 帧范围/fps/动作/fcurve 摘要/关键帧数 |
| set_frame_range | start, end, fps? |
| set_current_frame | frame |
| insert_keyframe | object, data_path(location/rotation_euler/scale/自定义路径), frame?, index?, value? |
| insert_keyframes_batch | object, keys: [{frame, location?, rotation?, scale?}] |
| delete_keyframe | object, data_path, frame, index? |
| list_keyframes | object, data_path? |
| set_interpolation | object, mode(CONSTANT/LINEAR/BEZIER/…), easing?, data_path?, frame_range? |
| add_fcurve_modifier | object, data_path, type(CYCLES/NOISE/LIMITS), settings? |
| assign_action | object, action?（空则新建） |
| nla_push_down | object |
| add_nla_strip | object, track?, action, frame_start, blend_type? |
| bake_animation | object, frame_start?, frame_end?, step?, visual_keying?, clear_constraints? |
| list_shape_keys | object |
| set_shape_key | object, name, value, frame?（给则打关键帧）；name 不存在则创建 |

### 5.7 Geometry Nodes（11）

| 工具 | 关键参数 |
|---|---|
| list_node_groups | type?(GEOMETRY/SHADER) |
| create_geometry_nodes | object, group_name?, modifier_name?：新建含 Group Input/Output 的树并挂 NODES 修改器 |
| get_node_tree | node_group → 节点/连线/接口 |
| add_geometry_node | node_group, type, name?, location?, inputs?, properties? |
| remove_geometry_node | node_group, node |
| link_geometry_nodes | node_group, from_node, from_socket, to_node, to_socket |
| unlink_geometry_nodes | node_group, to_node, to_socket |
| set_geometry_node_input | node_group, node, socket, value |
| add_group_socket | node_group, name, in_out(INPUT/OUTPUT), socket_type(NodeSocketFloat/…), default? |
| set_gn_modifier_input | object, modifier, input(按接口名), value：内部按名找 identifier |
| build_geometry_node_tree | node_group, nodes, links, clear? |

shader 与 geometry 的节点操作共用 `nodes_common.py`，只是入口按 material / node_group 取树。

### 5.8 Camera（7）

| 工具 | 关键参数 |
|---|---|
| list_cameras | — |
| get_camera_info | name |
| create_camera | name?, location?, rotation?, lens?, type?(PERSP/ORTHO), sensor_width?, clip_start?, clip_end?, set_active? |
| set_camera | name, lens?, type?, ortho_scale?, clip_start?, clip_end?, shift_x?, shift_y?, dof: {enabled, focus_object?, focus_distance?, fstop?}? |
| set_active_camera | name |
| point_camera_at | camera, target, use_constraint? |
| frame_objects | camera, objects, margin?：用包围球算距离，不依赖视口 |

### 5.9 Render（7）

| 工具 | 关键参数 |
|---|---|
| get_render_settings | — |
| set_render_settings | engine?, resolution?, percentage?, samples?, fps?, file_format?, color_mode?, output_path?, film_transparent?, motion_blur?, denoise?, engine_settings?（透传到 scene.eevee / scene.cycles） |
| set_color_management | view_transform?, look?, exposure?, gamma? |
| list_render_engines | — |
| render_image | output_path?, frame?, return_image?, max_preview_size? |
| render_animation | output_path, frame_start?, frame_end? |
| viewport_screenshot | output_path?, return_image?：仅 GUI |

### 5.10 Import/Export（5）

| 工具 | 关键参数 |
|---|---|
| import_file | path, format?(按后缀推断：obj/fbx/gltf/glb/usd/usda/usdc/stl/ply/abc/blend), options?, collection? → 返回新增对象名 |
| export_file | path, format?, objects?(默认全部), options? |
| append_from_blend | path, datablock(objects/materials/node_groups/collections/…), name, link? |
| save_blend | path?, compress? |
| open_blend | path, load_ui? |

### 5.11 UV & Texture（10）

| 工具 | 关键参数 |
|---|---|
| list_uv_maps | object |
| add_uv_map | object, name?, set_active? |
| remove_uv_map | object, name |
| unwrap_uv | object, method(ANGLE_BASED/CONFORMAL/SMART_PROJECT/CUBE/CYLINDER/SPHERE/LIGHTMAP), margin?, angle_limit?, uv_map? |
| pack_uv_islands | object, margin?, rotate? |
| mark_seams | object, edges?(索引列表), from_sharp?, clear? |
| create_image | name, width, height, color?, alpha?, float_buffer? |
| bake_texture | object, bake_type(DIFFUSE/NORMAL/AO/ROUGHNESS/EMIT/COMBINED), image?(不存在则按 size 新建), size?, output_path?, margin?, selected_to_active?, cage_extrusion?, samples? |
| save_image | image, path, format? |
| list_images | — |

### 5.12 Batch（8）

| 工具 | 关键参数 |
|---|---|
| batch_transform | objects, location?, rotation?, scale?, relative? |
| batch_rename | objects, prefix?, suffix?, find?, replace?, numbering? |
| batch_apply_material | objects, material |
| batch_add_modifier | objects, type, settings? |
| batch_set_property | objects, data_path, value：`obj.path_resolve` 写任意属性 |
| batch_delete | objects |
| distribute_objects | objects, mode(LINE/GRID/CIRCLE), spacing?, axis?, columns?, radius?, center? |
| randomize_transform | objects, location?, rotation?, scale?（各为 ±范围）, uniform_scale?, seed? |

### 5.13 Assets（8）

| 工具 | 关键参数 | 联网 |
|---|---|---|
| polyhaven_categories | asset_type(hdris/textures/models) | 是 |
| polyhaven_search | asset_type, categories?, query?, limit? | 是 |
| polyhaven_download | asset_id, asset_type, resolution?(1k/2k/4k), file_format?：HDRI→set_world_lighting；texture→create_pbr_material；model→import_file | 是 |
| sketchfab_search | query, categories?, count?, downloadable? | 是（token） |
| sketchfab_download | uid → glb 导入 | 是（token） |
| list_asset_libraries | — | 否 |
| search_local_assets | library?, type?(objects/materials/node_groups/worlds), query? | 否 |
| import_local_asset | library, name, type, link? | 否 |

Sketchfab token 存插件偏好；server 调 API 前用内部命令 `get_secret("sketchfab_token")` 取（不暴露为 MCP 工具），token 不写进仓库和配置文件。`get_blender_info` 只报告是否已配置。

### 5.14 Rigging（12）

| 工具 | 关键参数 |
|---|---|
| create_armature | name?, location?, bones: [{name, head, tail, parent?, roll?, connect?}] |
| list_bones | armature, pose?（带姿态变换） |
| add_bone | armature, name, head, tail, parent?, roll?, connect? |
| set_bone | armature, bone, head?, tail?, roll?, parent?, connect?, deform?, inherit_scale? |
| remove_bone | armature, bone |
| parent_to_armature | objects, armature, method(AUTOMATIC/ENVELOPE/EMPTY_GROUPS/DEFORM) |
| add_bone_constraint | armature, bone, type(IK/COPY_ROTATION/COPY_LOCATION/TRACK_TO/DAMPED_TRACK/LIMIT_ROTATION/…), settings? |
| set_pose | armature, bones: {name: {location?, rotation_euler?, rotation_quaternion?, scale?}}, keyframe?, frame? |
| reset_pose | armature, bones? |
| set_vertex_group_weights | object, group, weights: [[vertex_index, weight]] 或 all?, mode(REPLACE/ADD/SUBTRACT) |
| add_rigify_metarig | type(human/basic_human/basic_quadruped/…), name? |
| generate_rigify_rig | metarig |

Rigify 随 Blender 附带但默认未启用；`generate_rigify_rig` 会先确保启用。

### 5.15 Rig Diagnostics（7）

| 工具 | 说明 |
|---|---|
| check_rig | armature：孤儿骨、零长骨、deform 骨无对应顶点组、子网格未归一化权重、未应用缩放、约束目标丢失、骨名不对称；返回 `[{severity, code, bone?, message, fix_hint}]` |
| check_bone_hierarchy | armature → 树形结构 + 多根/循环检测 |
| check_bone_naming | armature, convention?(BLENDER `.L/.R`) → 缺失镜像、命名不规范 |
| find_unweighted_vertices | object, threshold? → 顶点索引列表 |
| get_bone_influence | object, vertex_index → 各组权重 |
| list_constraint_issues | armature → 目标为空/subtarget 不存在/链长越界的约束 |
| normalize_weights | object, lock_active?, groups? |

### 5.16 Scene Utilities（13）

| 工具 | 关键参数 |
|---|---|
| execute_code | code, return_var?：命名空间预置 bpy/bmesh/mathutils/math；捕获 stdout；返回 stdout + return_var 的 JSON 化结果 |
| get_blender_info | → 版本、Python、文件路径、已启用插件、插件版本、偏好里的 sketchfab token 是否配置 |
| get_api_docs | path(如 "bpy.types.Object.location" / "bpy.ops.mesh.primitive_cube_add") → 描述、类型、枚举项、默认值、子属性列表；从 bl_rna 读取，纯本地 |
| undo / redo | — |
| purge_orphans | — → 各类型清理数 |
| set_units | system?(METRIC/IMPERIAL/NONE), scale_length?, length_unit?, rotation_unit? |
| set_cursor | location?, rotation? |
| measure_distance | a, b（对象名或坐标） |
| get_bounding_box | objects, world?（合并包围盒 + 中心 + 尺寸） |
| ray_cast | origin, direction, distance? → 命中对象/位置/法线/面索引 |
| check_mesh | object → 顶点/边/面/三角数、非流形边、松散点、ngon 数、重复顶点估计 |
| mesh_cleanup | object, recalc_normals?, inside?, merge_by_distance?, threshold?, shade_smooth?, auto_smooth_angle?, dissolve_degenerate? |

### 5.17 Workflows（7）

| 工具 | 说明 |
|---|---|
| setup_three_point_lighting | target, distance?, height?, key_energy?, fill_ratio?, rim_ratio?, color_temp? → 创建 Key/Fill/Rim 三盏灯并指向目标 |
| setup_studio_scene | subject?, backdrop?(弧形背景板), ground?, hdri_path?, camera? |
| turntable_animation | object, frames?, revolutions?, camera?（为空则新建并 frame） |
| quick_product_render | object, output_path, resolution?, samples?, engine? → 三点光 + 相机取景 + 渲染 |
| material_from_texture_folder | folder, name?, assign_to?：按文件名关键字（basecolor/albedo/diffuse、roughness、metallic、normal、height/displacement、ao）识别贴图 |
| scatter_objects | source, surface, count?, seed?, scale_range?, align_to_normal?, method(GEOMETRY_NODES/COLLECTION_INSTANCES) |
| export_for_game | objects, path, format(FBX/GLB), apply_modifiers?, triangulate?, scale?, forward?, up? |

工作流工具在 handler 侧直接调用其他 handler 的 Python 函数，不走 socket 回环。

## 6. 错误处理

- handler 抛出的任何异常 → `{"ok": false, "error": {...}}`，traceback 完整回传；server 侧抛 `BlenderError`，FastMCP 以工具错误呈现，文本形如 `KeyError: Object 'Cub' not found. Did you mean: Cube, Cube.001`。
- 参数校验错误（枚举不对、插槽名不对、settings 键不对）在 handler 入口就报，并附带合法值列表；不让它一路跑到 bpy 再炸出难懂的信息。
- server 侧连接错误与超时是两种独立的错误类型，提示语区分「Blender 没起 server」和「操作太久」。
- `execute_code` 的异常同样结构化返回，不做任何过滤或沙箱——这是本地个人工具。

## 7. 测试

| 层 | 内容 | 依赖 |
|---|---|---|
| 对账 | server 工具名集合 == 插件非 internal 的 HANDLERS 集合；每个工具有非空描述 | 无 |
| server 单测 | 帧编解码、超时、错误映射、`resolve` 参数整形 | 无（假 socket） |
| 插件集成 | 每个类目一个 `test_<类目>.py`，通过真实 socket 打到 `Blender -b` | 本机 Blender |

集成 fixture（`tests/conftest.py`）：session 级启动
`/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tests/addon_boot.py -- --port <随机>`；
`addon_boot.py` 把 `addon/` 加进 `sys.path`，import 并 `register()`，起 server，然后用 `bpy.app.timers` 保活；
fixture 用 `ping` 轮询就绪（≤20 s），结束时发 `shutdown` 内置命令。每个测试函数前发 `reset_scene`（内部命令，`bpy.ops.wm.read_factory_settings()` 回到默认的 Cube/Light/Camera 场景）保证隔离。

需要 GUI 的工具（`viewport_screenshot`）测试标 `skip`，理由写清。Rigify 生成、烘焙、渲染各有一个最小用例（低采样、小分辨率）。
Poly Haven / Sketchfab 联网测试默认跳过，`BLENDER_MCP_ONLINE_TESTS=1` 时运行。

## 8. 安装与接入

```bash
cd /Users/panda/Documents/github/blender_mcp
uv sync
uv run blender-mcp-pro install-addon      # 软链 addon/blender_mcp_pro → ~/Library/Application Support/Blender/5.2/extensions/user_default/
                                          # 并用 blender -b 启用扩展 + 保存偏好；软链加载有问题时加 --copy 改为复制
claude mcp add --scope user blender-pro -- uv --directory /Users/panda/Documents/github/blender_mcp run blender-mcp-pro serve
```

之后打开 Blender（GUI），插件默认自动起 server；N 面板「MCP Pro」页可看状态、手动 Start/Stop。
开发时改了插件代码在 Blender 里 F3 → `Reload Scripts` 即生效；改了 server 代码重启 Claude Code 的 MCP 即可。

`docs/README.md` 写这些；`docs/tools.md` 由 `uv run blender-mcp-pro dump-tools` 生成。

## 9. 关键决策记录

| 决策 | 备选 | 理由 |
|---|---|---|
| 胖 addon + 薄 server | 薄 addon 拼代码字符串 / server 内嵌 Blender | 主线程安全、可无头测、真实 traceback |
| 只做 5.2 LTS | 兼容 4.2+ | 本机只有 5.2，个人用；省 ~20% 兼容层 |
| 长度前缀帧 | 换行分隔 / 括号配对 | 大图片 base64 不怕换行与嵌套 |
| 资产下载在 server 进程 | 在插件里下载 | 插件保持零联网、无第三方依赖；server 有 httpx |
| 节点工具按 material / node_group 分两套名字 | 一套名字带 tree_type 参数 | 对 LLM 更直观，实现共用 `nodes_common.py` 不重复 |
| 全部写操作 undo_push | 不管 | 用户在 GUI 里随时 Ctrl+Z 回退 AI 的操作 |
