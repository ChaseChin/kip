"""REPL 斜杠命令帮助（Markdown + Panel）。"""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from kip import __version__

HELP_MARKDOWN = f"""## 斜杠命令

> **当前版本：** `{__version__}`

| 命令 | 说明 |
|------|------|
| `/help` · 仅输入 `?`（无 `/`） | 完整说明（含下方 `config.yaml`） |
| `/h` · `/`?` | 速览：仅命令与要点，无配置说明 |
| `/exit` · `/quit` · `/q` | 退出 KIP，并显示会话摘要 |
| `/clear` | 清空**当前会话**消息（内存与 SQLite 中的本会话记录） |
| `/memory` · `/memory 关键词` | 搜索长期记忆；无关键词时匹配更多 |
| `/model` | 查看当前模型 |
| `/model 模型id` | 切换模型并写入 `config.yaml` |
| `/stats` | 查看本会话累计 Token（prompt / completion） |
| `/tools` | 列出当前已加载工具 |
| `/skills` | 列出已安装的 skill 目录（含 `skill.json`） |
| `/loaddev` | 从配置的 `paths.dev_md_path` 提炼 **DEV.MD** 到长期记忆（与上次内容相同则跳过） |
| `/loaddev force` | 强制重新提炼 DEV.MD（忽略「内容未变」跳过） |
| `/safety on` · `/safety off` | 开启 / 关闭危险操作前的确认（仍受 YOLO 等规则约束） |
| `/yolo` | 切换 **YOLO**（跳过大部分安全确认；删除等仍可能受限） |
| `/setup` · `/setup force` | 将 **config.yaml** 恢复默认后，进入与首次启动**相同**的 LLM 引导（模型 + API Key）；**不**删记忆库与日志；**永不**删除/覆盖/重建 SOUL、DEV、skills；`force` 跳过确认 |
| `/setup all` · `/setup all force` | 恢复默认 **config**、**删除**记忆库与日志后，同样进入首次启动式 **LLM 引导**；SOUL/DEV/skills 文件仍**永不**删除或重写；`force` 跳过确认 |

## 快捷键与提示

- **输入 `/`**：下方可出现**斜杠命令补全**（随输入过滤；**Tab** 选用当前候选；与普通输入兼容）。
- **Esc**：模型生成或工具链执行中可**取消**当前轮（见提示行）。
- **Shift+Tab**：切换 YOLO（与 `/yolo` 相同，见底栏状态）。
- **Ctrl+D**：在输入提示下**连按两次**才会结束会话并进入退出摘要（第一次仅提示「再按一次」）；若中间已输入内容并提交，会清除第一次计数。

## 启动参数

- **`--version`**：打印程序版本并退出。
- **`-d` / `--dev-md`**：本次启动时若存在 DEV.MD，则**提炼一次**到长期记忆（文件未变更则跳过，行为同 `/loaddev`）。
- **`-y` / `--yolo`**：以 YOLO 模式启动。
- **`-t` / `--trace`**：在终端**显示工具调用详情**（工具名与参数预览、步骤序号、成功时的结果摘要）。**默认关闭**（仅后台执行工具，终端不打印上述过程；工具失败时仍会打印错误行）。

---

## `config.yaml` 说明

**配置根目录**：相对路径（如 `data/kip_memory.db`、`SOUL.MD`）均相对于**本次使用的 `config.yaml` 所在目录**解析；若该文件尚不存在，则相对于 **`KIP_HOME`**（见下）对应的用户数据目录。

- **默认配置文件位置**：未设置 `KIP_CONFIG` 时，为 **`$KIP_HOME/config.yaml`**；未设置 `KIP_HOME` 时，`KIP_HOME` 由系统按惯例指向（Linux 多为 `~/.local/share/kip`，macOS/Windows 见各平台数据目录）。
- **`KIP_CONFIG`**：显式指定 `config.yaml` 路径；其**所在目录**即为配置根。
- **`KIP_HOME`**：用户级 KIP 根目录（默认 `config.yaml`、以及无配置文件时的相对路径锚点）。**本地开发**可设为克隆下来的仓库根，使行为与原先「工程目录」一致。
- **首次运行**：若默认位置尚无 `config.yaml`，启动时会先进入**首次向导**（创建示例 `SOUL.MD`、`DEV.MD`、`data/` 等并引导模型与 API Key）；若已有 `config.yaml` 但未设置 API Key 环境变量，则仅进入密钥/模型补充引导。

### `llm`（模型）

| 配置项 | 说明 |
|--------|------|
| `model` | 模型名（如 `qwen3.6-plus`）；与 `/model` 切换写入同一字段 |
| `base_url` | 兼容 OpenAI 的 API 地址；空则走各厂商默认 |
| `api_key_env` | 读取 API Key 的**环境变量名**（默认 `KIP_LLM_APIKEY`）；密钥本身只放在该环境变量中，**勿写入** YAML |
| `max_output_tokens` | 单次回复最大生成 token 上限 |
| `temperature` | 采样温度 |
| `context_window` | 上下文窗口提示（展示/约束；默认 `65536`；可改为 `null` 关闭展示） |

### `memory`（记忆库）

| 配置项 | 说明 |
|--------|------|
| `db_path` | SQLite 库路径（相对**配置根**或绝对路径） |
| `max_history_messages` | 注入对话上下文的**最近消息条数**上限 |
| `auto_extract_long_term` | 是否在每轮回复后**后台**从对话中提炼长期记忆（额外 LLM 调用） |
| `long_term_inject_max` | 写入 **system** 的**全局长期记忆**条数上限；`0` 表示不注入（仍会写入库） |
| `dev_md_max_chars` | `/loaddev`、`-d` 时送入模型的 **DEV.MD 最大字符数**（超出截断） |

### `safety`（安全）

| 配置项 | 说明 |
|--------|------|
| `enabled` | 是否对非安全工具启用**确认**（与 `/safety`、YOLO 配合） |
| `browser_allowed_hosts` | 浏览器类工具允许访问的主机名列表（空则按工具逻辑） |

### `mcp`（MCP 服务）

| 配置项 | 说明 |
|--------|------|
| `servers` | MCP 子进程服务列表（`name` / `command` / `args` / `env` 等）；启动时尝试加载为工具 |

### `paths`（路径与日志）

| 配置项 | 说明 |
|--------|------|
| `cwd` | 部分工具（如 shell）使用的**工作目录** |
| `skills_dir` | 可安装 skill 的根目录（相对**配置根**或绝对路径） |
| `soul_path` | **人设 / 规则** Markdown；可被 **`KIP_SOUL`** 覆盖为其它文件 |
| `dev_md_path` | **DEV.MD** 路径；可被 **`KIP_DEV_MD`** 覆盖 |
| `log_path` | 运行日志文件（轮转）；相对**配置根**或绝对路径 |
| `log_level` | 日志级别，如 `INFO`、`DEBUG`；也可用 **`KIP_LOG_LEVEL`** 覆盖 |

### 环境变量速查

| 变量 | 作用 |
|------|------|
| `KIP_HOME` | 用户级 KIP 根目录；默认 `config.yaml` 路径为 `$KIP_HOME/config.yaml`，且无配置文件时相对路径相对此目录 |
| `KIP_CONFIG` | 指定配置文件路径（其所在目录为配置根） |
| `KIP_SOUL` | 覆盖 `paths.soul_path` |
| `KIP_DEV_MD` | 覆盖 `paths.dev_md_path` |
| `KIP_LOG_LEVEL` | 覆盖 `paths.log_level` |
| `KIP_TIMING` | 设为 `1` / `true` 时在终端输出阶段耗时（排查性能） |
| `KIP_LLM_APIKEY` | 默认的 LLM API Key（与 `llm.api_key_env` 一致时生效；也可在配置里把 `api_key_env` 改成其它变量名） |
"""

HELP_SHORT_MARKDOWN = f"""## 命令速览

> **当前版本：** `{__version__}`

| 命令 | 说明 |
|------|------|
| `/help` | 完整说明（含 `config.yaml`） |
| `/h` · `/`?` | 本速览（短） |
| `/exit` · `/quit` · `/q` | 退出 |
| `/clear` | 清空本会话消息 |
| `/model` | 查看或切换模型 |
| `/memory` | 搜索长期记忆 |
| `/loaddev` · `/loaddev force` | DEV.MD → 长期记忆（`force` 强制） |
| `/tools` · `/skills` | 工具列表 · 已安装 skill |
| `/stats` | 本会话 Token |
| `/safety on` · `off` · `/yolo` | 安全确认 · YOLO |
| `/setup` · `/setup all` | 重置后走首次同款 LLM 引导 · `all` 另删库与日志（不碰 SOUL/DEV/skills） |

## 要点

- **/**：斜杠命令补全（下方候选、**Tab** 选用）· **Esc**：生成中取消 · **Shift+Tab**：YOLO（见底栏）
- **Ctrl+D** 连按两次退出；启动可加 **`-d`**（导入 DEV.MD）、**`-y`**（YOLO）、**`-t`**（显示工具调用详情）
"""


def print_repl_help_short(console: Console) -> None:
    console.print()
    console.print(
        Panel(
            Markdown(HELP_SHORT_MARKDOWN),
            title="[bold bright_cyan]KIP Agent · 速览[/]",
            border_style="bright_blue",
            padding=(1, 2),
            title_align="left",
        )
    )


def print_repl_help(console: Console) -> None:
    console.print()
    console.print(
        Panel(
            Markdown(HELP_MARKDOWN),
            title="[bold bright_cyan]KIP Agent · 使用说明[/]",
            border_style="bright_blue",
            padding=(1, 2),
            title_align="left",
        )
    )
