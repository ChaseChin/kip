# KIP CLI (`kip-cli`)

<p align="center">
  <b>EN</b> — A terminal-first conversational AI agent for developers: memory, tools, optional skills &amp; MCP.<br/>
  <b>中文</b> — 面向开发者的对话式命令行 AI Agent，支持会话记忆、工具调用、可选 Skill 与 MCP。
</p>

---

## Table of contents · 目录

| | EN | 中文 |
|---|----|------|
| 1 | [Overview](#overview--概述) | [概述](#overview--概述) |
| 2 | [Requirements](#requirements--环境要求) | [环境要求](#requirements--环境要求) |
| 3 | [Installation](#installation--安装) | [安装](#installation--安装) |
| 4 | [Configuration](#configuration--配置) | [配置](#configuration--配置) |
| 5 | [Usage](#usage--运行) | [运行](#usage--运行) |
| 6 | [Development](#development--开发) | [开发](#development--开发) |
| 7 | [License](#license--许可证) | [许可证](#license--许可证) |

---

## Overview · 概述

### English

**KIP** is an interactive CLI agent built with **prompt_toolkit** and **Rich**. It talks to LLMs via **LiteLLM** (OpenAI-compatible APIs), persists chat and long-term memory in **SQLite**, can load **MCP** servers as tools, and supports installing **skills** from Git/HTTP/local paths. Configuration is YAML-based; secrets stay in environment variables.

### 中文

**KIP** 是基于 **prompt_toolkit** 与 **Rich** 的交互式命令行 Agent，通过 **LiteLLM** 调用兼容 OpenAI 的 API，使用 **SQLite** 保存会话与长期记忆，可加载 **MCP** 服务作为工具，并支持从 Git / HTTP / 本地目录安装 **Skill**。配置使用 YAML；密钥通过环境变量提供。

---

## Requirements · 环境要求

| | English | 中文 |
|---|---------|------|
| **Python** | 3.10+ | 3.10 及以上 |
| **Browser tools** | Chromium via Playwright (optional) | 若使用浏览器类工具，需安装 Playwright 的 Chromium（可选） |

---

## Installation · 安装

### From PyPI · 从 PyPI 安装（推荐）

包名 **`kip-cli`**，已发布在：**https://pypi.org/project/kip-cli/**

**English** — Install from **pypi.org** (no extra index flags needed):

```bash
pip install kip-cli
# pin version if needed: pip install "kip-cli==0.5.0"
playwright install chromium   # optional, browser tools
```

**中文** — 从 **正式 PyPI** 安装（一般无需额外 `--index-url`）：

```bash
pip install kip-cli
# 固定版本示例：pip install "kip-cli==0.5.0"
playwright install chromium   # 可选，浏览器相关工具
```

升级：`pip install -U kip-cli`。

### From source · 从源码安装

**English**

```bash
git clone <your-fork-or-repo-url> kip
cd kip
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
playwright install chromium        # optional
```

**中文**

```bash
git clone <仓库地址> kip
cd kip
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
playwright install chromium        # 可选
```

**源码安装排错（`pip install -e ".[dev]"`）**

| 情况 | 说明 |
|------|------|
| **必须在仓库根目录执行** | 含 `pyproject.toml` 的目录；若在其他路径，需写绝对路径：`pip install -e "/path/to/kip[dev]"`。 |
| **zsh 下 `[dev]` 被当成通配** | 务必加引号：`pip install -e ".[dev]"` 或 `pip install -e '.[dev]'`；否则可能报 `zsh: no matches found`。 |
| **`mcp` / `litellm` 等 (from versions: none)** | 与 TestPyPI 无关，但**同样受本机 pip 源配置影响**（仅镜像、仅 TestPyPI、`PIP_INDEX_URL` 等）。可先：`pip install -e ".[dev]" --extra-index-url https://pypi.org/simple`，或 `pip config list` 后调整 `pip.conf`。 |
| **Python 版本** | 需要 **≥ 3.10**（见 `pyproject.toml` 的 `requires-python`）。 |

### From TestPyPI · 从 TestPyPI 试装（可选）

**一般用户请用上文「从 PyPI 安装」**；本节仅供维护者验证 **TestPyPI** 上的预发布或试装包。

**English** — TestPyPI does **not** mirror all dependencies. Use **both** indexes so **kip-cli** can be pulled from TestPyPI while **dependencies** resolve from PyPI:

```bash
pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple \
  "kip-cli==0.5.0"
```

**中文** —

- 正式版已在 **pypi.org**；只有当你要装 **仅发布在 TestPyPI** 上的构建时，才需要下面**双索引**（否则会出现依赖 `from versions: none` 等问题）。
- TestPyPI **不会**镜像全部依赖，**必须**同时加 `--extra-index-url https://pypi.org/simple`。

```bash
pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple \
  "kip-cli==0.5.0"
```

示例（独立 venv）：`python3 -m venv .venv-pip`，再执行（版本号与 TestPyPI 上实际一致）：  
`.venv-pip/bin/pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple "kip-cli==0.5.0"`。

#### Troubleshooting · 排错

| 现象 | 原因 | 处理 |
|------|------|------|
| `Could not find ... mcp>=0.1.0 (from versions: none)` | 依赖（`mcp`、`litellm` 等）**只在 pypi.org**；若 pip **只**连了 TestPyPI，解析依赖时会找不到包。 | 安装命令**必须**同时包含 `--extra-index-url https://pypi.org/simple`。 |
| 同上，且你**已经写了** `--extra-index-url` 仍报错 | 多半是**本机 pip 全局配置**覆盖了行为：例如 `~/.pip/pip.conf` / `/etc/pip.conf` 里只配置了 `index-url`（镜像或 TestPyPI），或环境变量 **`PIP_INDEX_URL`** 指向单一源；pip 会优先/合并这些配置，导致依赖仍只在错误索引上解析。 | 执行 `pip config list` 查看生效项；安装时**临时**取消环境变量：`env -u PIP_INDEX_URL pip install ...`；或在 `pip.conf` 的 `[global]` 里增加 **`extra-index-url = https://pypi.org/simple`**（与现有 `index-url` 并存）。 |
| `pip is looking at multiple versions of kip-cli...` | 在为主包找兼容版本时，因某依赖装不上而不断回退尝试旧版 `kip-cli`。 | 同上，先保证 **pypi.org 参与依赖解析**。 |

---


## Configuration · 配置

### API key · API 密钥

| | English | 中文 |
|---|---------|------|
| **Rule** | Put the real key in the environment variable named by `llm.api_key_env` in `config.yaml` (default: **`KIP_LLM_APIKEY`**). Do not commit secrets. | 真实密钥放在 `config.yaml` 中 `llm.api_key_env` 所指的环境变量里（默认 **`KIP_LLM_APIKEY`**），勿把密钥写入 YAML 或提交仓库。 |
| **Example** | `export KIP_LLM_APIKEY="sk-..."` | `export KIP_LLM_APIKEY="sk-..."` |

### Paths & `config.yaml` · 路径与配置文件

| Variable · 变量 | English | 中文 |
|-----------------|---------|------|
| **`KIP_HOME`** | User-level root. Default config file is `$KIP_HOME/config.yaml`. Relative paths in YAML resolve against the **directory of that config file**; if the file does not exist yet, they resolve against `KIP_HOME`. | 用户级根目录；默认配置文件为 `$KIP_HOME/config.yaml`。YAML 中的相对路径相对**该配置文件所在目录**解析；若文件尚不存在，则相对 `KIP_HOME` 解析。 |
| **`KIP_CONFIG`** | Explicit path to `config.yaml`. Its parent directory becomes the **config root** for relative paths. | 显式指定 `config.yaml` 路径；其**所在目录**为相对路径的配置根。 |
| **Neither set** | Uses OS user data dir (via `platformdirs`), e.g. on macOS often `~/Library/Application Support/kip/config.yaml`. | 未设置时，使用系统用户数据目录（`platformdirs`），例如 macOS 上多为 `~/Library/Application Support/kip/config.yaml`。 |

**English — Local development tip:** point `KIP_HOME` at your cloned repo root so `data/`, `SOUL.MD`, etc. match your project layout.

**中文 — 本地开发建议：** 将 `KIP_HOME` 设为克隆下来的仓库根目录，使 `data/`、`SOUL.MD` 等与工程结构一致。

**From Git clone · 从 Git 克隆源码时：** 仓库内提供 **`config.example.yaml`**。在仓库根目录执行 `cp config.example.yaml config.yaml` 后按需编辑；首次启动若尚无 `config.yaml`，仍会进入向导生成配置。默认 **不** 提交 `config.yaml`、`SOUL.MD`、`DEV.MD` 及 `data/` 下数据库与日志（见 `.gitignore`）。

Optional overrides: **`KIP_SOUL`**, **`KIP_DEV_MD`**, **`KIP_LOG_LEVEL`**, **`KIP_TIMING`**. See `/help` inside the REPL for details.

### First run · 首次运行

| | English | 中文 |
|---|---------|------|
| **When** | If the default **`config.yaml`** does not exist yet (typical after a fresh `pip install`), KIP runs a **first-run wizard** before the REPL. | 若默认位置的 **`config.yaml`** 尚不存在（例如刚 `pip install` 后），启动时会先进入**首次运行向导**，再进入 REPL。 |
| **What it does** | Creates `data/`, skills root, sample **`SOUL.MD`**, **`DEV.MD`**, and a short **`README.txt`** under the config directory; then prompts for model preset and API key (key stays in the process env only). | 在配置目录下创建 `data/`、skills 目录、示例 **`SOUL.MD`**、**`DEV.MD`** 及 **`README.txt`**，再交互选择模型并输入 API Key（密钥仅写入当前进程环境变量）。 |
| **Note** | If **`config.yaml` already exists**, the wizard is skipped; only the “missing API key” flow may run. | 若 **`config.yaml` 已存在**，则不再跑首次向导；仅在未检测到 API Key 环境变量时进入补充引导。 |

---

## Usage · 运行

### Basic · 基本用法

**English**

```bash
kip              # interactive REPL
kip --version    # print version and exit
kip -y           # start with YOLO (fewer safety prompts)
kip -d           # on startup, ingest DEV.MD into long-term memory (if file present)
kip -t           # show tool-call trace (steps, args preview, success summaries); hidden by default
```

**中文**

```bash
kip              # 交互式 REPL
kip --version    # 打印版本号并退出
kip -y           # 以 YOLO 模式启动（减少安全确认）
kip -d           # 启动时若存在 DEV.MD，则提炼到长期记忆
kip -t           # 显示工具调用详情（步骤、参数预览、成功摘要）；默认不显示
```

### Slash commands · 斜杠命令（节选）

| Command · 命令 | English | 中文 |
|----------------|---------|------|
| `/help` · `/h` | Full or short help; **shows current package version** | 完整或速览帮助；**显示当前版本号** |
| `/model` | Show or switch model | 查看或切换模型 |
| `/memory` | Search long-term memory | 搜索长期记忆 |
| `/clear` | Clear current session messages | 清空本会话消息 |
| `/loaddev` | Ingest DEV.MD into long-term memory | 将 DEV.MD 提炼到长期记忆 |
| `/setup` · `/setup all` | Re-run LLM setup like first launch; `all` also clears DB + log (never deletes SOUL/DEV/skills files) | 按首次启动流程重配 LLM；`all` 另删记忆库与日志（不删 SOUL/DEV/skills 文件） |
| `/skills` · `/tools` | List skills / tools | 列出 skill / 工具 |

Type `/help` in the REPL for the full list (incl. `/stats`, `/safety`, `/yolo`, etc.).

---

## Development · 开发

### English

- Run tests: `pytest` (see `pyproject.toml` → `[tool.pytest.ini_options]`).
- Lint / types: `ruff`, `mypy` (optional extras in `[dev]`).
- Release: `python -m build`, then `twine upload` **only** the `dist/kip_cli-<version>.tar.gz` and matching `py3-none-any.whl` for the `version` in `pyproject.toml` (do not upload unrelated files left in `dist/`). Configure PyPI / TestPyPI API tokens per [twine](https://twine.readthedocs.io/) docs.
- Deeper architecture, rules, and changelog-style notes: [KIP.MD](KIP.MD).

### 中文

- 运行测试：`pytest`（配置见 `pyproject.toml` 中 `[tool.pytest.ini_options]`）。
- 代码风格与类型检查：可选用 `ruff`、`mypy`（`[dev]` 可选依赖）。
- 发布到 PyPI / TestPyPI：先 `python -m build`，再使用 **twine** 上传与 `pyproject.toml` 中 `version` **一致**的两件制品：`dist/kip_cli-<version>.tar.gz` 与 `dist/kip_cli-<version>-py3-none-any.whl`（勿把 `dist/` 里其它旧版本一并上传）。Token 与 `twine` 用法见官方文档。
- 项目规则、需求与更详细的架构说明见 [KIP.MD](KIP.MD)。

---

## License · 许可证

MIT — see [LICENSE](LICENSE).

---

<p align="center"><sub>Package name on PyPI: <code>kip-cli</code> · Command: <code>kip</code></sub></p>
