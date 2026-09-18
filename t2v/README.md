# t2v —— 工作台的 Python 包

在 `remote_t2v/` 根目录用 `python3 -m t2v <命令>`。所有命令共用一棵 argparse 树（`cli.py`），
业务逻辑在各模块里；库代码抛 `errors.py` 里的异常，只有 `cli.main` 把它翻成退出码 2。

## 命令

| 命令 | 费用 | 作用 |
|---|---|---|
| `init <slug> [--title]` | 免费 | 从 `projects/_template` 建新项目 |
| `validate <项目> [镜头]` | 免费 | 校验 project.json、prompt 六字段、输入文件是否齐 |
| `plan <项目> <镜头>` | 免费 | 建图、导出画布、打印帧数（dry-run，不联网提交）；报价默认不算，要看加 `--quote` |
| `run <项目> <镜头> --execute --generation-confirmed` | **付费** | 与用户确认 prompt 版本与工作流后提交生成；报价默认不算，个别项目要强制报价在 `project.json` 写 `generation_confirmation.quote = "required"` |
| `run <项目> <镜头> --execute --generation-confirmed` | **付费** | 报价可选的项目：确认生成内容后提交生成 |
| `review / promote / pack <项目> …` | 免费 | 六审表、交付晋级、可迁移打包 |
| `migrate-v1 <项目> [--execute]` | 免费 | 旧项目按 v2 布局只复制迁移 |
| `flux <项目> <生图 prompt>` | **占卡** | FLUX.2 [klein] 出一张图（场景底板/首帧图）；不传 `--execute` 就是免费 dry-run |
| `graph flux <项目> <生图 prompt> --out …` | 免费 | 只建 FLUX.2 的 API 图并导出，不联网 |
| `h3 --workflow … [--dry-run \| --execute --cost-confirmed]` | 视参数 | 直接调 H3 引擎；报价可选项目带 `--project` 时改用 `--generation-confirmed` |
| `scail2 --project … --mode maskcheck\|full` | 视参数 | SCAIL-2 角色替换实验 |
| `graph h3` / `graph scail2 …` | 免费 | 重建工作流 API JSON，不联网 |
| `motion` / `contact-sheet` | 免费 | 参考片运镜量化、产物并排接触表（需 OpenCV/NumPy） |

镜头级临时覆盖：`--version --duration --megapixels --aspect --steps --seed`，只影响本次，不写回 prompt。

## 模块

顶层只放**与引擎无关**的东西；任何一个模型专有的知识都在它自己的 `engines/<name>/` 里。

| 模块 | 职责 |
|---|---|
| `cli.py` / `__main__.py` | 项目级命令与装配；引擎子命令由引擎自己注册；异常 → 退出码 |
| `cliopts.py` | 项目命令与引擎共用的 argparse 片段（客户端选项、费用闸门、镜头覆盖） |
| `errors.py` | `T2VError` 及 `ProjectError` / `PromptError` / `GraphError` / `ComfyError` / `CostGuardError` |
| `paths.py` | `ROOT` / `PROJECTS` / `WORKFLOWS` / `CLIENT_CACHE` |
| `frontmatter.py` | prompt 顶部 YAML 风格 frontmatter 的解析（**通用**，不含任何模型字段） |
| `project.py` | 项目配置、路径与资产别名解析、新项目初始化 |
| `runs.py` | run 目录选取、六审表、交付晋级、打包 |
| `media.py` | ffprobe 探测与评审版重定时 |
| `provenance.py` | 输入 SHA-256 与仓库状态，写进 run 记录 |
| `migration.py` | v1 → v2 只复制迁移（一次性代码，三个 v1 项目迁完即可删） |
| `comfy/client.py` | ComfyUI HTTP：上传、提交、轮询、下载、浏览器会话 id |
| `comfy/graph.py` | 图节点查找/构造与 `.ui.json` 画布同步 |
| `engines/__init__.py` | **引擎注册表与契约**（见下） |
| `engines/capsule.py` | run capsule 落盘与 `index.jsonl` 登记（所有引擎共用） |
| `engines/h3/` | `request` 请求类型与报价、`prompt` 六段校验与 17k+5、`graph` 建图（纯函数）、`runner` 执行、`official` 重建官方图、`cli` 命令行表面 |
| `engines/scail2/` | 同上结构；**不支持项目-镜头工作流**，只有实验入口 |
| `analysis/` | 参考片运动测量与并排接触表（可选依赖 OpenCV） |

## 引擎即插件

加一个引擎 = 新建 `engines/<name>/` + 在 `engines/__init__.py` 的 `REGISTRY` 加一行。
**不需要改 `cli.py`，也不需要改任何顶层模块。**

**通用契约**（所有引擎必须导出）：

| 导出 | 作用 |
|---|---|
| `NAME` | 与 `REGISTRY` 的键一致，也是 `project.json` 里 `engine.name` 的取值 |
| `add_arguments(sub)` | 注册 `t2v <NAME> …` 子命令，并 `set_defaults(func=…)` |
| `add_graph_arguments(sub)` | 注册 `t2v graph <NAME> …` 子命令 |

**项目-镜头契约**（支持 `t2v plan/run <项目> <镜头>` 的引擎才导出，要么全有要么全无）：

| 导出 | 作用 |
|---|---|
| `from_project(slug, shot, overrides)` | → 请求对象，需带 `.meta`（prompt frontmatter） |
| `validate(request)` | → `(errors, warnings)` |
| `quote(request)` | → 免费报价文案 |
| `plan(request)` | 免费：建图、导出画布、打印计划 |
| `execute(request, client, cost_confirmed)` | 付费：提交、轮询、下载、记账 |

`cli.project_engine()` 读 `project.json` 的 `engine.name`（缺省 `h3`）来分发。
引擎只实现通用契约时（如 SCAIL-2 以「实验」为单位，没有镜头版本那一层），
`t2v plan <项目>` 给出明确提示而不是崩在 `AttributeError`；
`tests/test_engines.py` 把「项目契约要么全有要么全无」钉成了测试。

## 费用纪律

`plan`、`graph`、`validate` 与引擎的 `--dry-run` 都不联网提交。任何会占用 GPU 的命令都要求：
默认项目先展示本轮报价、拿到用户明确确认，再显式传 `--execute --cost-confirmed`。
`languid-afternoon` 在 `project.json` 将报价设为可选：`plan` 显示 prompt、工作流、参数与参考资产，
需要金额时加 `--quote`；确认生成内容后传 `--execute --generation-confirmed`。
`h3_runner.execute()` 与 `scail2_runner.execute()` 签名上还有一道 `cost_confirmed`，
防止绕过 CLI 直接调用。该内部布尔值表示已按项目策略取得确认；**代码保护不能代替真实确认。**

## 测试

```bash
python3 -m pytest            # 63 条，全部离线；付费链路用假 ComfyUI 覆盖，引擎契约有专门一组
```

`tests/conftest.py` 把 `paths.PROJECTS` 指向临时目录并从模板造项目，
项目级测试不依赖真实作品的版本号；只有 `test_cli.py` 里留一条对仓库现役镜头的冒烟校验。
测试文件与模块一一对应：`test_frontmatter` / `test_h3_{prompt,request,graph,runner}` / `test_scail2_graph` / `test_engines` / `test_runs` / `test_cli`。
