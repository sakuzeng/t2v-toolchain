# ComfyUI 工作流

三种角色，分开放，不要混：

| 目录 | 角色 | 谁读它 | 能不能改 |
|---|---|---|---|
| `h3/*.api.json` | **提交用的 API 图**，`t2v` 填值后发给 ComfyUI | `t2v h3` / `t2v run` | 只能由 `t2v graph h3` 重建，或从 ComfyUI 重新导出 |
| `h3/*.ui.json` | **本工作台在用的画布版**，与同名 API 图配对 | `comfy/graph.py` 的画布同步 | 在浏览器里重存后覆盖；必须与 API 图同名 |
| `templates/` | **官方原样捕获**，只读参考与重建时的接线依据 | 人、`t2v graph h3` | 不改。要改先另存到 `h3/` |

## `h3/` —— 当前在用

| 文件 | 来源 | 用途 |
|---|---|---|
| `t2v.api.json` | ComfyUI 里跑通官方 T2V 模板后 `Save (API Format)` 导出（2026-09-06） | 文生视频基线；`projects/{smoke,guofeng-pov}/run.sh` 直接用 |
| `t2v.ui.json` | 同一张画布在 ComfyUI 0.34.5 下重存（比 0.33.0 的官方模板多了 `SaveVideo.codec` 与 `CreateVideo` 色彩空间两个控件） | T2V 画布模板 |
| `r2v.api.json` | **构建产物**：`python3 -m t2v graph h3` 由 `t2v.api.json` + `templates/minimax-h3/video_minimax_h3_r2v.json` 的接线推出 | 参考图生视频基线；全部 v2 项目的 `engine.workflow` |
| `r2v.ui.json` | 官方 R2V 模板的副本（ComfyUI 0.33.0，与 `templates/` 下那份当前逐字节相同） | R2V 画布模板 |

节点 id 与官方画布模板保持一致，画布同步才能按旧值替换控件。四图等多图输入不写在文件里，
由 `t2v/engines/h3/graph.py` 在请求中加入（`<Picture N>` 依次占 137 / 139 / 922 / 923）。

`r2v.ui.json` 与官方模板现在是同一份内容，但**不合并**：`templates/` 是永不改动的捕获，
`h3/` 是会随 ComfyUI 版本重存而漂移的在用版（`t2v.ui.json` 已经漂了）。两边一比就知道差在哪。

## `templates/` —— 官方捕获，只读

`templates/<引擎>/<任务>.json`。全部抓于 2026-09-06，节点标注 ComfyUI 0.33.0。
文件名按**任务**命名，不带引擎前缀——目录已经说明了引擎，上游原名记在下表里。

| 文件 | 内容 | 上游模板名 |
|---|---|---|
| `minimax-h3/t2v.json` | 官方 T2V | `video_minimax_h3_t2v` |
| `minimax-h3/r2v.json` | 官方 R2V（`t2v graph h3` 的接线依据） | `video_minimax_h3_r2v` |
| `minimax-h3/i2v.json` | 官方 I2V（首帧 / 首尾帧 / 尾帧） | `video_minimax_h3_i2v` |
| `minimax-h3/i2v_continuation.json` | 官方 I2V 续写 | `video_minimax_h3_i2v_continuation` |
| `minimax-h3/multiframe_reference.json` | 官方多帧参考；**`t2v` 不再接这条**，关键帧锚点已随深度控制退役 | `video_minimax_h3_multiframe_reference` |
| `flux2/klein_character_multiview.json` | Flux2 Klein 角色多视图（图像模型，与 H3 视频链路无关；当前无代码引用，供角色资产设计参考） | ComfyUI 模板浏览器 |

### 新模板往哪放

增长发生在**引擎这一层**，不在引擎内部：上游每个模式只出一个模板，而新的**引擎**会不断来
（`docs/research/MOTION_TRANSFER.md` 里待捕获的 SCAIL-2 `video_wan21_scail2_character_replacement_int8`、
Wan Animate 2 都是新引擎）。规则：

1. 新引擎 → 新建 `templates/<engine-slug>/`，小写连字符，与 `h3/`、`docs/` 里的写法一致。
2. 引擎目录内**平铺**，按任务命名（`t2v` / `r2v` / `i2v` / `replacement` …），上游原名写进上面的表。
3. 只有当**同一个任务**攒够 3 个及以上变体时，才给那个任务开子目录
   （例如 `minimax-h3/i2v/{basic,continuation,first_last}.json`）。在那之前不分——
   5 个文件分 4 个目录，目录比内容还多。
4. 某个引擎从"参考"升级为"在用"时，在 `h3/` 旁边新建 `<engine>/` 放它的 API 图与配对画布；
   `templates/` 那份永远不动，留作漂移对照。

## 其他引擎

SCAIL-2 不存文件：官方模板的 Base 子图由 `t2v/engines/scail2/graph.py` 在内存里展开，
用 `python3 -m t2v graph scail2 --out <路径>` 落盘查看。

赤翎旧 FunControl/guide 共享模板已于 2026-09-16 随深度控制路线一起删除
（理由见 `docs/research/CAMERA_REPLICATION.md` 文首）；历史运行证据仍在对应 run capsule，
旧分析文档与 run sidecar 里的工作流路径只代表当时的流程，不再可解析。

## 运行真值

项目镜头由 `project.json` 的 `engine.workflow` 选工作流。`python3 -m t2v plan <项目> <镜头>`
免费导出同步了本次参数的项目画布到 `projects/<项目>/workflows/`；真正提交时会把实际 API 图、
prompt 与输入哈希冻结进 run capsule。**CLI 请求是运行真值**，画布出现模板占位警告时，
先核对输入再手动使用。
