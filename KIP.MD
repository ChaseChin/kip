# KIP CLI Agent - 项目规则与需求

> 📌 **使用说明**：本文件为 **KIP** 项目的**规则与需求**说明，亦为 AI 与开发者协作时的主要依据。请严格按照本文件的架构、规范与路线图分步实现，禁止跳跃实现或擅自修改技术栈。**每次修改代码后必须同步更新本文档（`KIP.MD`）。**

---

## 🎯 项目概述

| 项目 | 说明 |
|------|------|
| **名称** | `kip-cli` |
| **版本** | 与 `pyproject.toml` 的 `version` 同步（发布时递增；当前示例见仓库内 `pyproject.toml`） |
| **定位** | 面向个人开发者的对话式命令行 AI Agent |
| **核心交互** | 用户通过自然语言对话驱动 Agent，Agent 自动规划并执行任务 |
| **执行能力** | 内置 Skill、MCP 协议接入、本地系统操作、浏览器自动化、天气查询 |
| **过程可视化** | 执行过程中实时输出任务步骤、工具调用、中间结果与最终状态 |
| **记忆系统** | 基于 SQLite 持久化对话历史、工具执行日志、长期记忆与上下文状态 |
| **分发安装** | PyPI 包名 **`kip-cli`**（[pypi.org/project/kip-cli](https://pypi.org/project/kip-cli/)）；`pip install kip-cli`；版本与 `pyproject.toml` 的 `version` 一致；浏览器工具需额外 `playwright install chromium` |

---

## 📋 核心需求清单

| 模块 | 需求说明 |
|------|----------|
| **对话驱动** | REPL 交互，支持自然语言输入与 `/help`、`/clear`、`/memory`、`/model`、`/setup`、`/setup all`、`/yolo` 等控制命令 |
| **多引擎执行** | 统一工具路由：Skill（自定义函数）、MCP（外部服务器）、Local（文件/Shell/Git）、Browser（网页交互/抓取）、Weather（天气查询） |
| **步骤与结果输出** | 实时流式打印执行计划、工具调用参数、成功/失败状态、返回摘要 |
| **SQLite 记忆** | 持久化：历史对话、Tool 调用记录、用户偏好、关键上下文摘要、支持按会话/关键词检索 |
| **安全门控** | 本地写操作/Shell/Browser 动作默认拦截，展示预览后需 y/n 确认（可切换免确认模式） |
| **YOLO 模式** | 启动参数 `-y/--yolo` 或 `/yolo` 命令跳过安全确认（删除操作除外） |
| **全异步架构** | 所有 I/O（LLM、DB、子进程、浏览器、网络）必须基于 async/await，禁止阻塞主循环 |

---

## 🏗 技术架构设计

### 项目结构
```
kip-cli/
├── config.yaml              # 配置文件
├── pyproject.toml           # 依赖管理
├── tests/                   # pytest 测试（pythonpath=src，见 pyproject.toml）
├── data/
│   └── kip_memory.db        # SQLite 数据库
├── examples/
│   ├── mcp_server.py        # 示例 MCP 服务器
│   └── skill_echo/          # 示例动态 skill（skill.json + echo_tools.py）
├── README.md
├── KIP.MD                   # 项目规则、需求、模块表与变更记录（本文件）
├── SOUL.MD                  # Agent 人设 / 规则 / 能力（启动读入，可改 paths.soul_path）
└── src/kip/                 # Python 包名 kip（可编辑安装：pip install -e .）
    ├── __init__.py          # 版本号 __version__
    ├── config.py            # 配置管理 (pydantic + pyyaml)；API Key 仅经环境变量（见 llm.api_key_env）
    ├── memory.py            # 记忆系统 (aiosqlite)，时间戳为北京时间 UTC+8
    ├── llm_client.py        # LLM 客户端 (litellm，模块级设置 LITELLM_LOCAL_MODEL_COST_MAP)
    ├── agent.py             # Agent 状态机 + 工具集成
    ├── cli.py               # REPL (prompt_toolkit + KeyBindings、底部状态栏、Shift+Tab)
    ├── main.py              # 入口：argparse（--version / -y / -d / -t）、asyncio.run(..., debug=False)、环境变量
    ├── emitter.py           # 步骤输出 + LLM 等待时 Live Spinner
    ├── safety.py            # 安全门控
    ├── model_selector.py    # 首次启动与 /setup：模型预设、API Key 仅写入当前进程环境变量（不落盘密钥）
    ├── banner.py            # 启动欢迎界面（Logo + 配置摘要）
    ├── branding.py          # 助手回复面板（KIP Agent Logo + Markdown）
    ├── repl_common.py       # REPL 共享：execute_repl_line、命令解析
    ├── repl_help.py         # /help、/h 的 Markdown 帮助（含当前版本号）
    ├── repl_completer.py    # 斜杠命令 Tab/输入时补全（SlashCommandCompleter）
    ├── repl_cancel.py       # Esc 取消长时间任务（与 execute_repl_line 配合）
    ├── memory_extract.py    # 长期记忆 LLM 提取 → upsert 全局 memories
    ├── soul.py              # 读取 SOUL.MD → 注入 Agent 系统提示
    ├── skills/              # 动态 Skill：安装、manifest、运行时加载
    │   ├── manifest.py      # skill.json → SkillManifest
    │   ├── loader.py        # import 技能模块、SkillToolWrapper 前缀
    │   └── install.py       # 本地目录 / zip / git / http zip → data/skills/<id>/
    ├── mcp/                 # MCP 客户端
    │   ├── __init__.py
    │   └── client.py        # stdio 发现工具、代理 BaseTool
    └── tools/               # 工具模块
        ├── __init__.py      # default_tools 惰性导入，避免与 MCP 循环依赖
        ├── base.py          # 工具基类 BaseTool
        ├── file_io.py       # 文件读写
        ├── shell_exec.py    # Shell 执行
        ├── browser.py       # 浏览器自动化
        ├── weather.py       # 天气查询 (wttr.in)
        ├── applescript.py   # macOS osascript / AppleScript
        └── skill_hub.py     # install_skill、list_skills（动态注册到 Agent）
```

**本地开发**：`pip install -e ".[dev]"` 后在项目根执行 `pytest`；仅未安装可编辑包时可用 `PYTHONPATH=src pytest`。安装后入口命令：`kip`。

**自动化测试（推荐每次改代码后执行）**：

```bash
pip install -e ".[dev]"
pytest
```

测试目录为 `tests/`（pytest），覆盖配置、记忆库、REPL 解析、工具、`run_applescript`、Skill 安装加载、Agent `merge_tools` 等（不依赖真实 LLM API）。

### 核心设计原则
- **统一工具契约**：所有执行器实现 `BaseTool`，包含 `name`, `description`, `schema`, `is_safe`, `async execute(args)`
- **显式步骤输出**：使用 `rich.status` / `rich.console` 实时渲染 `📝 步骤 N: ... → ✅ 完成 / ❌ 失败: ...`
- **记忆分层**：
  - 短期：当前会话消息列表（内存）
  - 中期：SQLite `tool_logs` 记录（可回溯/重试）
  - 长期：SQLite `memories` 表（用户偏好、关键知识、自动摘要）
- **安全优先**：非只读操作强制走 `dry_run → 预览 → 确认 → 执行` 流程（YOLO 模式除外）
- **多轮工具链**：Agent 支持连续执行多个工具调用，根据结果自动决定下一步
- **可观测性**：结构化日志 + 步骤事件流 + Token 消耗追踪

---

## 🛠 技术栈选型

| 模块 | 推荐库 | 版本要求 | 理由 |
|------|--------|----------|------|
| **CLI/REPL** | `prompt_toolkit` + `rich` | ≥3.0.36 / ≥13.7.0 | 完整 REPL、流式高亮、中断安全 |
| **LLM 适配** | `litellm` | ≥1.35.0 | 统一接口、自动流式解析、百模型兼容 |
| **MCP 客户端** | `mcp` (Python SDK) | ≥0.1.0 | 官方协议实现，支持 stdio/sse 传输 |
| **浏览器自动化** | `playwright` (async) | ≥1.40.0 | 现代 Web 交互标准，原生异步支持 |
| **配置管理** | `pydantic` + `pyyaml` | ≥2.6 / ≥6.0 | 强类型校验、自动序列化 |
| **数据库** | `aiosqlite` | ≥0.20.0 | 异步 SQLite，零阻塞记忆读写 |
| **文件 I/O** | `aiofiles` | ≥23.2.0 | 安全异步文件操作 |
| **代码规范** | `ruff` + `mypy` | ≥0.3.0 / ≥1.8.0 | 快速 lint + 严格静态类型检查 |

---

## 📐 模块划分与职责

| 模块 | 文件 | 状态 | 职责 |
|------|------|------|------|
| **配置管理** | `config.py` | ✅ 已完成 | 加载/保存 YAML 配置，pydantic 校验 |
| **记忆系统** | `memory.py` | ✅ 已完成 | 异步 SQLite，会话历史/工具日志/长期记忆 |
| **LLM 客户端** | `llm_client.py` | ✅ 已完成 | litellm 封装，流式/非流式调用，provider 自动推断 |
| **Agent** | `agent.py` | ✅ 已完成 | 状态机，多轮工具链，上下文构建 |
| **REPL** | `cli.py` | ✅ 已完成 | prompt_toolkit 交互，控制命令解析 |
| **程序入口** | `main.py` | ✅ 已完成 | argparse：`--version`、`-y`/`--yolo`、`-d`/`--dev-md`、`-t`/`--trace`；`asyncio.run(run_repl, debug=False)` |
| **步骤输出** | `emitter.py` | ✅ 已完成 | Rich 实时渲染步骤状态 |
| **安全门控** | `safety.py` | ✅ 已完成 | 风险评估，y/n 确认机制 |
| **模型选择器** | `model_selector.py` | ✅ 已完成 | 首次启动与 `repl_llm_reconfigure`（`/setup`），预设模型列表；密钥仅环境变量 |
| **工具基类** | `tools/base.py` | ✅ 已完成 | BaseTool 契约，OpenAI 格式转换 |
| **文件工具** | `tools/file_io.py` | ✅ 已完成 | 异步读写文件 (aiofiles) |
| **Shell 工具** | `tools/shell_exec.py` | ✅ 已完成 | 安全命令执行 (危险命令拦截) |
| **浏览器工具** | `tools/browser.py` | ✅ 已完成 | Playwright 封装，页面导航/截图/提取/点击/填写 |
| **天气工具** | `tools/weather.py` | ✅ 已完成 | wttr.in 天气查询，支持中文 |
| **MCP 客户端** | `mcp/client.py` | ✅ 已完成 | MCP 协议客户端，stdio 传输，工具适配 |
| **启动欢迎** | `banner.py` | ✅ 已完成 | Rich Panel：Logo、版本、模型、接口、YOLO、SOUL 路径摘要等 |
| **回复区品牌** | `branding.py` | ✅ 已完成 | `assistant_reply_panel`：Logo 条 + Markdown 正文 |
| **REPL 调度** | `repl_common.py` | ✅ 已完成 | `ReplBundle`、`execute_repl_line`、Slash 命令（含 `/setup` / `/setup all`）与对话统一入口 |
| **动态 Skill** | `skills/`、`tools/skill_hub.py` | ✅ 已完成 | 安装 skill 包、启动加载、`Agent.merge_tools` |

---

## 📝 开发规则与规范（必须遵守）

### 代码规范
- ✅ **类型提示强制**：所有函数/类必须带完整类型注解，通过 `mypy --strict` 检查
- ✅ **纯异步 I/O**：禁止在 async 函数中使用阻塞调用（`open()`, `subprocess.run()`, `time.sleep()`, 同步 playwright 等）
- ✅ **错误处理**：顶层 try/except 捕获，打印用户友好提示（不默认输出完整 traceback），禁止静默失败
- ✅ **提交规范**：遵循 Conventional Commits，每次提交附验证命令
- ✅ **文档同步**：每次修改代码后必须更新 `KIP.MD`
- ✅ **Git 与隐私**：通过 `.gitignore` 排除虚拟环境、本地 `config.yaml`、`SOUL.MD` / `DEV.MD`、`data/` 下数据库与日志等；仓库内仅保留 `config.example.yaml` 作为配置模板

### 工具安全门控
- `is_safe=False` 的工具执行前必须调用 `safety.confirm(action_desc)`
- **YOLO 模式**：`-y/--yolo` 启动参数或 `/yolo` 命令可跳过大部分确认（删除操作除外）
- Shell 限制 cwd、超时 30s、拦截 `| > ;` 等管道符
- Browser 操作需限制域名白名单（可配置）与最大页面数

### 多轮工具链规范
- Agent 支持循环执行工具调用，直到 LLM 返回最终回复
- 每次工具调用必须构造正确的 OpenAI Tool Call 格式：
  ```python
  # assistant 消息
  {"role": "assistant", "content": None, "tool_calls": [...]}
  # tool 消息 (必须包含 tool_call_id 和 name)
  {"role": "tool", "tool_call_id": "call_xxx", "name": "tool_name", "content": "..."}
  ```

### 步骤输出规范
```
📝 步骤 N: 描述...
✅ 完成: 结果摘要
❌ 失败: 错误信息
```

### SQLite 使用规范
- 必须使用 `aiosqlite`，所有 DB 操作异步化
- 表结构需包含 `id`, `session_id`, `created_at`, `payload`, `status`
- 提供上下文窗口自动清理策略（保留最近 N 轮或按 Token 截断）

---

## 🗺 迭代路线图

> ⚠️ **严格按顺序实现**，每阶段完成后提供可运行的最小验证命令。

| 阶段 | 目标 | 交付物 | 验证命令 | 状态 |
|------|------|--------|----------|------|
| **Phase 1** | 脚手架 + 配置管理 + SQLite 记忆初始化 + 基础 REPL | config.yaml 读写、/model 命令、SQLite 表创建、对话循环框架 | `pytest` | ✅ 已完成 |
| **Phase 2** | LLM 流式客户端 + Agent 状态机基础 | litellm 封装、流式逐字输出、Idle→Thinking→Reply 闭环 | `pytest` | ✅ 已完成 |
| **Phase 3** | 本地工具 + 步骤输出系统 | file_io, shell_exec 实现、emitter 实时渲染步骤/结果、安全确认 | `pytest` | ✅ 已完成 |
| **Phase 4** | 浏览器操作集成 | playwright 异步封装、页面导航/元素提取/截图、安全门控 | `pytest` | ✅ 已完成 |
| **Phase 5** | MCP 客户端桥接 | 连接外部 MCP Server、动态发现工具、统一路由注册 | `pytest` | ✅ 已完成 |
| **Phase 6** | 记忆增强 + 生产打磨 | 长期记忆存取、历史摘要、Token 预算控制、异常恢复/中断处理 | `pytest` | ✅ 已完成 |

---

## 📊 开发进度

### ✅ 已完成模块 (Phase 1-6 全部完成)

| 类别 | 模块 | 文件 |
|------|------|------|
| 🔧 **核心** | 配置管理 | `config.py` |
| | 记忆系统 | `memory.py` |
| | LLM 客户端 | `llm_client.py` |
| | Agent 状态机 | `agent.py` |
| | REPL 交互 | `cli.py` |
| | 程序入口 | `main.py` |
| 📺 **输出** | 步骤输出系统 | `emitter.py` |
| 🔒 **安全** | 安全门控 | `safety.py` |
| 🎯 **模型** | 模型选择器 | `model_selector.py` |
| 🛠 **工具** | 工具基类 | `tools/base.py` |
| | 文件读写 | `tools/file_io.py` |
| | Shell 执行 | `tools/shell_exec.py` |
| | 浏览器自动化 | `tools/browser.py` |
| | 天气查询 | `tools/weather.py` |
| 🔗 **MCP** | MCP 客户端 | `mcp/client.py` |
| 🖼 **UI** | 启动欢迎 / 回复品牌 | `banner.py` / `branding.py` |
| 🔄 **REPL** | 命令与对话共用逻辑 | `repl_common.py` |
| 📖 **帮助** | `/help` / `/h` Markdown 与版本展示 | `repl_help.py` |
| ⏹ **取消** | Esc 监听与任务取消 | `repl_cancel.py` |

### 🎊 项目状态

**✅ 所有 6 个阶段已完成！**

| 阶段 | 状态 | 测试 |
|------|------|------|
| Phase 1: 脚手架 + 基础 REPL | ✅ 完成 | `pytest` |
| Phase 2: LLM 流式客户端 | ✅ 完成 | `pytest` |
| Phase 3: 本地工具 + 步骤输出 | ✅ 完成 | `pytest` |
| Phase 4: 浏览器操作集成 | ✅ 完成 | `pytest` |
| Phase 5: MCP 客户端桥接 | ✅ 完成 | `pytest` |
| Phase 6: 模型配置 + 生产打磨 | ✅ 完成 | `pytest` |

### 🆕 Phase 6 后迭代（与本仓库一致）

| 功能 | 说明 | 状态 |
|------|------|------|
| **错误提示** | REPL / Agent / 工具失败仅输出简短说明，不打印 Python 堆栈 | ✅ |
| **思考动画** | `emitter.thinking()`：Rich Live + 轮换文案 + 耗时 | ✅ |
| **启动欢迎** | `banner.print_welcome`：Logo、版本、模型、base_url、api_key_env、max_output、context、YOLO、记忆库路径 | ✅ |
| **回复区品牌** | `branding.assistant_reply_panel` + `emitter.markdown_reply` | ✅ |
| **底部状态栏** | 模型、`max_output`、**`context window=`**（原 `context_window` 配置）、YOLO、Shift+Tab、`/help`；**不**展示 SQLite 路径；**不**展示 Esc 提示（避免过长） | ✅ |
| **Shift+Tab** | `Keys.BackTab`（`eager=True`）切换 Normal / YOLO | ✅ |
| **asyncio 调试** | `PYTHONASYNCIODEBUG=0`、`asyncio.run(..., debug=False)`、`run_repl` 内 `set_debug(False)`，避免 `run_in_executor` + 阻塞输入误报慢回调 | ✅ |
| **LiteLLM 成本图** | `LITELLM_LOCAL_MODEL_COST_MAP=true`（`main.py` 与 `llm_client` 模块级 `setdefault`），减轻首次拉取 GitHub 失败告警 | ✅ |
| **惰性导入** | `litellm` 在 `llm_client` 内延迟导入；`tools.default_tools` 惰性加载，减轻 MCP/Playwright 导入链 | ✅ |
| **首次引导与 Key** | `needs_setup` 检测 `llm.api_key_env` 所指环境变量；`repl_llm_reconfigure` 供 `/setup` 复用首次同款交互；**密钥不落盘 YAML** | ✅ |
| **`/setup` / `/setup all`** | `save_config(AppConfig())` 后走 `repl_llm_reconfigure`；`all` 另删记忆库与日志并新会话；`cli.py` 中 `_apply_setup_config_only` / `_apply_setup_all` | ✅ |
| **`--version`** | `main.py` argparse `action="version"`；`/help` 与 `/h` 面板内展示 `kip.__version__` | ✅ |
| **发布** | `python -m build` 后使用 **twine** 仅上传与 `pyproject.toml` 中 `version` 匹配的 `dist/kip_cli-<version>.tar.gz` 与对应 `py3-none-any.whl`（勿上传 `dist/` 中其它旧版本文件）；Token 见 PyPI / TestPyPI 文档 | ✅ |
| **配置字段** | `llm.max_output_tokens`、`llm.context_window`；API Key **仅**经 `api_key_env` 环境变量提供 | ✅ |
| **数据库时间** | 记忆库时间字段使用北京时间 (UTC+8) | ✅ |
| **Markdown 回复** | Panel + Markdown（表格、代码块等） | ✅ |
| **YOLO / 天气 / 多轮工具** | 见上文核心需求与工具表 | ✅ |

**未在本仓库实现（可作为后续优化，勿与上表混为一谈）**：双击 Ctrl+D 退出流程的专项文档化、`/skill` 别名、流式工具调用专项测试文档等。（**Esc** 取消当前轮已在 `repl_cancel.py` + `execute_repl_line` 中实现。）

---

## 📌 全量更新说明（实现与配置，与代码同步）

### 环境变量

| 变量 | 作用 |
|------|------|
| `KIP_LLM_APIKEY` 等 | 由 `config.yaml` 的 `llm.api_key_env` 指定变量名；**密钥只放在环境变量**，勿写入 YAML |
| `LITELLM_LOCAL_MODEL_COST_MAP` | 设为 `true` 时使用本地模型成本映射，避免 LiteLLM 首次联网拉取失败 |
| `PYTHONASYNCIODEBUG` | 入口设为 `0`，关闭 asyncio 调试噪声 |
| **`KIP_SOUL`** | 若设置，指向 SOUL 人设文件绝对路径，**优先于** `paths.soul_path` |

### `config.yaml` 要点（`LLMConfig`）

- `model`、`base_url`、`api_key_env`、`max_output_tokens`、`temperature`、`context_window`
- **密钥**：仅通过 `api_key_env` 所指环境变量提供，**不**在 YAML 中保存 API Key

**`MemoryConfig`**：`db_path`、`max_history_messages`、**`auto_extract_long_term`**（默认 true，每轮助手最终回复后调用 LLM 提取事实写入 `memories` 且 `session_id` 为空表示跨会话）、**`long_term_inject_max`**（注入 system prompt 的条数，0 表示不注入）。

**`PathsConfig.soul_path`**：默认 `SOUL.MD`（项目根），Markdown；启动时读入并注入系统提示 **「## 人设与规则（SOUL）」**，位于内置基座提示之后、长期记忆之前；欢迎面板显示是否加载成功。

### 长期记忆（实现说明）

- 表 **`memories`**：`session_id IS NULL` 表示全局长期记忆；`list_global_memories_latest` / `upsert_global_memory` 按 key 去重保留最新。
- **`memory_extract.maybe_extract_long_term_memories`**：在 `Agent.run_turn` 得到**无 tool_calls 的最终回复**后异步执行；失败静默忽略。
- 系统提示词会附带「## 长期记忆（跨会话）」列表（受 `long_term_inject_max` 限制）。

### 动态 Skill（`paths.skills_dir`，默认 `data/skills`）

- 每个 skill 为独立目录，根目录含 **`skill.json`**（`id` / `module` / `factory`）及 **`{module}.py`**，其中 `factory(cwd) -> list[BaseTool]`。
- 安装目录名必须等于 **`skill.json` 的 `id`**；工具在 LLM 中可见名为 **`{id}__{原工具名}`**。
- **`install_skill`**（`is_safe=False`）：`source` 支持本地目录、本地 `.zip`、git URL、`https` 指向的 zip；成功后 `Agent.merge_tools` 立即注册。
- **`list_skills`**：列出已安装 skill 元数据；启动时 **`load_installed_skill_tools_report`** 自动加载并合并进工具表（失败行 stderr 告警）。
- 示例：`examples/skill_echo/`。

### REPL 行为摘要

- **单会话 PromptSession**（无分屏 REPL；已移除实验性 split 方案）
- **命令**：`/help`、`/h`（速览）、`/clear`、`/memory`、`/model`、`/loaddev`、`/setup`、`/setup all`、`/yolo`、`/stats`、`/tools`、`/skills`、`/safety`、`/exit` 等（实现见 `repl_common.py`；帮助正文见 `repl_help.py`，含当前版本号）
- **补全**：输入 `/` 后由 `repl_completer.SlashCommandCompleter`（prompt_toolkit）提供命令与子命令（如 `/setup ` → `all` / `force`）候选，支持随输入过滤与 **Tab** 选用
- **快捷键**：`Shift+Tab` 切换 YOLO；**Esc** 在生成中可取消当前轮（`repl_cancel`）；`Ctrl+C` / `Ctrl+D` 等见上文表

### 关键文件职责速查

| 文件 | 职责 |
|------|------|
| `main.py` | argparse（`--version`、`-y`、`-d`、`-t`/`--trace`）、环境变量、`asyncio.run(run_repl, debug=False)` |
| `cli.py` | `run_repl`：`set_debug(False)`、底部栏、YOLO 绑定、调用 `repl_common` |
| `repl_common.py` | Slash 命令与用户输入统一处理 |
| `emitter.py` | 步骤输出、思考 Live、`markdown_reply` |
| `llm_client.py` | LiteLLM 调用、`LITELLM_LOCAL_MODEL_COST_MAP` |
| `model_selector.py` | 首次配置、`interactive_setup`、`repl_llm_reconfigure`（`/setup`） |
| `memory.py` | `MemoryStore`、全局长期记忆读写 |
| `memory_extract.py` | 从单轮对话 LLM 提取并 `upsert_global_memory` |

---

## 🤖 AI 协作执行指引

### 工作流程
1. 读取本文件，确认当前需求和规范
2. 输出涉及文件清单、实现策略，等待确认后再输出代码
3. 每次只实现一个模块/功能，代码需完整可运行，包含必要注释与类型提示
4. 禁止堆砌未经验证的依赖，优先使用上述指定技术栈
5. **每次修改代码后必须更新 `KIP.MD`**

### 技术规范
- 工具调用格式必须兼容 OpenAI Function Calling / Tool Use 规范
- 流式解析需处理 litellm 分片累积问题，使用缓冲队列确保 JSON 完整后再提交给执行器
- 步骤输出必须通过 `emitter.py` 统一调度，禁止直接 `print()` 混入主逻辑
- SQLite 操作必须异步，连接池复用，事务自动提交/回滚
- 多轮工具链必须构造正确的 `tool_calls` 和 `tool` 消息格式
- 遇到歧义时：列出 2-3 种可行方案，说明权衡点，不要自行假设

### 交付要求
每次生成后必须提供：
1. 依赖安装命令（含 `playwright install` 等系统级步骤）
2. 启动与测试步骤
3. 预期输出示例
4. 已知限制与后续优化点
5. **更新 `KIP.MD` 文档**

---

## 🚀 启动与使用

### 安装（PyPI）

正式包已发布，包名 **`kip-cli`**：

```bash
pip install kip-cli
# 固定版本示例：pip install "kip-cli==0.5.0"
pip install -U kip-cli   # 升级
```

使用浏览器类工具前（可选）：`playwright install chromium`。  
维护者从 **TestPyPI** 试装、从 **源码** 可编辑安装等，见仓库 **`README.md`** 对应章节。

### 基本启动
```bash
kip
kip --version    # 打印版本并退出（版本号同 `kip.__version__` / `pyproject.toml`）
```

### YOLO 模式 (跳过安全确认)
```bash
kip -y
# 或
kip --yolo
```

### 工具调用 Trace（终端显示详情）
默认不在终端打印单步工具过程；需要调试或观察调用链时使用：
```bash
kip -t
# 或
kip --trace
```
效果：显示工具名与参数预览、步骤序号、成功时的结果摘要；失败时即使未加 `-t` 也会打印错误提示。

### REPL 命令
| 命令 | 功能 |
|------|------|
| `/help` · `/h` | 完整帮助或速览；**文内含当前版本号** |
| `/clear` | 清空当前会话 |
| `/model [ID]` | 查看/切换模型 |
| `/memory [关键词]` | 查看/搜索记忆 |
| `/loaddev` · `/loaddev force` | 将 DEV.MD 提炼到长期记忆 |
| `/setup` · `/setup all` | 按首次启动流程重配 LLM；`all` 另删记忆库与日志（不删 SOUL/DEV/skills 文件） |
| `/stats` | 查看 Token 使用统计 |
| `/tools` | 查看已注册工具列表 |
| `/skills` | 列出已安装 skill（元数据） |
| `/safety [on/off]` | 切换安全确认模式 |
| `/yolo` | 切换 YOLO 模式 |
| `/exit` 或 `/quit` | 退出程序 |

### 快捷键
| 快捷键 | 功能 |
|--------|------|
| `Esc` | 模型生成或工具执行中可取消当前轮 |
| `Ctrl+C` | 中断当前操作 |
| `Ctrl+D` | 连按两次退出（见 `/help`） |
| `↑/↓` | 浏览历史命令 |
| **`Shift+Tab`** | **切换 Normal/YOLO 模式** |

### 支持的模型提供商

**API Key**：KIP 只从 `config.yaml` 里的 **`llm.api_key_env`** 所指环境变量读取密钥，**默认变量名为 `KIP_LLM_APIKEY`**；与具体提供商无绑定，也**不会**自动读取 `OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`DEEPSEEK_API_KEY`、`DASHSCOPE_API_KEY` 等。若希望与某工具习惯一致，可自行在配置里把 `api_key_env` 改成对应名称并 `export`。密钥勿写入 YAML。

| 提供商 | 模型 ID 示例 |
|--------|----------------|
| OpenAI | `gpt-3.5-turbo`, `gpt-4`, `gpt-4o` |
| Anthropic | `claude-3-sonnet-20240229`, `claude-3-opus-20240229` |
| DeepSeek | `deepseek-chat` |
| **阿里云百炼** | `qwen-turbo`, `qwen-plus`, `qwen-max`, `qwen-coder-plus`；首次引导与 `/setup` 预设亦含 `qwen3.6-plus` 等 |

### 已注册工具
| 工具名称 | 功能 | 安全 |
|----------|------|------|
| `read_file` | 读取文件内容 | ✅ |
| `write_file` | 写入文件 | ❌ |
| `shell_exec` | 执行 Shell 命令 | ❌ |
| `run_applescript` | macOS 执行 AppleScript（osascript） | ❌ |
| `get_weather` | 查询天气 (wttr.in) | ✅ |
| `browser_navigate` | 打开网页 | ❌ |
| `browser_screenshot` | 页面截图 | ✅ |
| `browser_extract` | 提取页面内容 | ✅ |
| `browser_click` | 点击页面元素 | ❌ |
| `browser_fill` | 填写输入框 | ❌ |
| `install_skill` | 安装 skill 包（本地/git/http zip）并注册工具 | ❌ |
| `list_skills` | 列出已安装 skill（读 skill.json） | ✅ |
| `{skill_id}__…` | 各 skill 提供的工具（名称带前缀） | 依 skill |

---

## 📅 变更记录（汇总）

| 日期 | 内容 |
|------|------|
| **2026-04-12** | **文档命名**：原 `CLAUDE.MD` 更名为 **`KIP.MD`**，作为本项目的规则与需求主文档；README 链接与文内引用已同步。 |
| **2026-04-12** | 文档：将 Phase 6 后「与本仓库一致」的功能整理进本文件；新增「全量更新说明」；项目结构补充 `banner.py`、`branding.py`、`repl_common.py`、`mcp/`；模块表补充欢迎/品牌/REPL 调度；未实现项单独标注，避免与已实现功能混淆。 |
| **2026-04-12** | 行为：底部状态栏曾含 SQLite 路径，后已移除以缩短行宽，改为展示 **context window** 文案；助手回复使用 **`branding.assistant_reply_panel`**；启动 **`banner.print_welcome`**；**Shift+Tab** 切换 YOLO（`Keys.BackTab`）；**asyncio** `debug=False` + `set_debug(False)` + `PYTHONASYNCIODEBUG=0`；**LiteLLM** `LITELLM_LOCAL_MODEL_COST_MAP`；**首次引导**与 **`/setup`**：`repl_llm_reconfigure`，密钥仅环境变量；**错误**不打印堆栈；移除分屏 REPL 实验代码。 |
| **2026-04-12** | **CLI**：`--version`；**帮助**：`repl_help` 展示 `__version__`；**发布**：`twine` 仅上传当前 `pyproject.toml` 版本对应两件制品；**文档**：README / `KIP.MD` 同步上述与 `/setup` 说明；修正「API Key 仅环境变量」表述。 |
| **2026-04-12** | **长期记忆**：`memory_extract` + `upsert_global_memory`；每轮最终回复后可选 LLM 提取写入全局 `memories`；`long_term_inject_max` 注入 system prompt；配置 `auto_extract_long_term` / `long_term_inject_max`。 |
| **2026-04-12** | **动态 Skill**：`skills/*` + `install_skill` / `list_skills`；`paths.skills_dir`；启动加载已安装 skill；`Agent.merge_tools` / `list_tools`；`/skills`；示例 `examples/skill_echo`。 |
| **2026-04-12** | **AppleScript**：内置工具 `run_applescript`（仅 macOS，`osascript -e`；`is_safe=False`）。 |
| **2026-04-12** | **测试**：`tests/` + pytest；`pip install -e ".[dev]"` 后 `pytest`。 |
| **2026-04-14** | **仓库**：`scripts/` 纳入 `.gitignore` 不再提交（发布、TestPyPI 试装等维护者本地保留）；README / 本文件改为说明 `pytest` 与 **twine** 发布流程。 |
| **2026-04-15** | **分发**：`kip-cli` 已发布 **正式 PyPI**；`KIP.MD` / `README.md` 补充 `pip install kip-cli` 与升级说明；TestPyPI 仅作可选试装说明。 |
| **2026-04-12** | **文档**：「支持的模型提供商」修正为与实现一致：API Key 仅经 `llm.api_key_env`（默认 `KIP_LLM_APIKEY`），非各厂商独立环境变量名。 |
| **2026-04-12** | **SOUL**：根目录 `SOUL.MD` + `soul.py`；`paths.soul_path` / `KIP_SOUL`；`Agent(soul_markdown=…)`；欢迎面板显示加载状态。 |

> **当前状态**：本仓库按 `KIP.MD` 所述完成 **从零脚手架**（`src/kip`、Phase 1–6 测试、示例 MCP）。核心 REPL / Agent / 工具 / MCP 可运行。  
> **后续可选**：流式工具缓冲专项测试、退出会话摘要的额外文档等（见上文「未在本仓库实现」）。
