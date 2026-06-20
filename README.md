<h1 align="center">
  <img src="assets/brand/roxy-logo.png" alt="ROXY" width="520">
</h1>

<p align="center">
  <strong>TUI-first vertical research agent with OKF knowledge and controlled evolution.</strong>
  <br>
  <sub>持续监控信息源，沉淀结构化知识，并用评估闭环让 Agent 可验证地变好。</sub>
</p>

<p align="center">
  <a href="https://github.com/IBN-Spring/Roxy/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="#"><img src="https://img.shields.io/badge/version-0.6.0-green.svg" alt="Version 0.6.0"></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-238%20passed-brightgreen.svg" alt="238 Tests"></a>
</p>

<p align="center">
  <b>中文</b> | <a href="README_en.md">English</a>
</p>

---

Roxy 是一个面向垂直领域研究的 Agent CLI/TUI。它不是一次性搜索工具，而是一个长期运行的研究工作台：持续追踪 RSS、ArXiv、PubMed、网页和微信公众号等来源，把发现写入受 Google OKF 思路启发的结构化知识库，再通过聊天、搜索、摘要和评估闭环帮助你不断积累领域知识。

Roxy 的目标是做一个更像 Claude Code / Hermes 的终端 Agent，但核心场景不是写代码，而是 **自主调研、知识沉淀和受控自进化**。

## 核心特点

### 1. Controlled Evolution Engine

Roxy 会记录真实交互轨迹，从失败案例生成 eval seeds，运行 baseline，输出改进建议，并比较候选版本是否真的变好。

它不会自动覆盖 prompt、工具描述或核心代码。所有进化都必须经过：

```text
trace -> eval seeds -> eval run -> proposal -> compare -> human review
```

这让 Roxy 的改进不是“感觉更聪明了”，而是能看到提升、退化和风险。

### 2. Google OKF-inspired Knowledge Store

Roxy 使用 OKF v0.1 作为知识沉淀格式，设计思路参考 Google OKF：把来源、条目、主题、洞察和采集方式变成可验证的结构，而不是散落在聊天记录里的文本。它支持 JSON Schema 校验、JSONL 导入导出、SQLite + FTS5 搜索和重复内容去重。

知识库不是聊天记录堆积，而是可迁移、可验证、可查询的结构化研究资产。

```bash
roxy knowledge search "spatial transcriptomics"
roxy knowledge export --out kb.jsonl
roxy knowledge validate kb.jsonl
```

### 3. Full-network Research Intake

Roxy 的网络能力不是单个 web fetch，而是一层可扩展的研究采集协议。它通过统一 Channel 协议接入多种信息来源：

| Channel | 状态 | 用途 |
|---------|------|------|
| `rss` | ready | 任意 RSS / Atom feed |
| `arxiv` | ready | ArXiv 学术论文 |
| `pubmed` | ready | PubMed / NCBI 论文 |
| `wechat` | config | 微信公众号，只读适配 wechat-query SQLite |
| `agent_reach_web` | external | 通过 Agent-Reach CLI 扩展网页能力 |

Channel 有统一的 `check()`、`collect()`、`repair_hint()` 和 capability summary。外部能力通过 adapter 接入，Roxy core 保持干净。

### 4. TUI-first Research Workbench

Roxy 的主入口是终端 TUI，不需要在一堆命令之间来回跳。你可以在聊天界面里完成采集、查询、摘要、状态检查和 session 恢复。

```text
/status          总览模型、知识库、频道、最近采集
/feeds           查看信息源状态
/collect         采集所有 enabled feeds
/collect topics  采集保存的研究方向
/runs            查看采集历史
/digest          生成最近 7 天研究摘要
/kb <query>      搜索知识库
/model           查看或切换模型
```

### 5. Persistent Domain Monitoring

Roxy 可以保存长期关注的研究方向，然后定时监控：

```bash
roxy research topics add "single cell RNA-seq" --channels arxiv,pubmed
roxy research topics add "large language models" --channels arxiv
roxy monitor run --json
```

一次 monitor run 会同时处理 feeds 和 topics，生成 run history，后续可以按 run 出 digest 或回溯采集结果。

## 快速开始

```bash
git clone https://github.com/IBN-Spring/Roxy.git
cd Roxy
pip install -e ".[tui]"

roxy init --yes --name "你的名字" --domain "生物信息学"
roxy config set models.providers.deepseek.api_key "sk-..."
roxy chat
```

也可以使用环境变量：

```bash
export DEEPSEEK_API_KEY="sk-..."
roxy chat
```

如果没有配置 API key，Roxy 会在 TUI、`/key` 和 `roxy doctor` 中给出修复命令。

## 典型工作流

### 持续追踪一个领域

```bash
roxy research topics add "spatial transcriptomics" --channels arxiv,pubmed
roxy monitor run
roxy research digest --days 7 --out weekly.md
roxy knowledge search "cell atlas"
```

### 监控自己的信息源

```bash
roxy research feeds add "Hacker News" "https://hnrss.org/frontpage"
roxy research feeds add "ArXiv ML" "http://export.arxiv.org/rss/cs.LG"
roxy research collect --all
roxy research runs latest
```

### 在 TUI 中完成研究闭环

```bash
roxy chat

/collect
/runs
/digest latest
/kb protein folding
```

### 受控自进化

```bash
roxy eval seeds generate --out seeds.jsonl
roxy eval run seeds.jsonl --out baseline.json
roxy eval propose baseline.json --out proposals.md
roxy eval run seeds.jsonl --out candidate.json
roxy eval compare baseline.json candidate.json
```

## 架构

```text
roxy chat
  |
  +-- Textual TUI
  |     +-- slash commands
  |     +-- visible tool calls
  |     +-- session resume
  |
  +-- QueryEngine
  |     +-- ModelProvider       多 provider 接入
  |     +-- ContextManager      system prompt + profile + compaction
  |     +-- ToolExecutor        权限检查 + 并行工具调用
  |     +-- SessionManager      会话持久化
  |
  +-- Tools
        +-- file_read           workspace-bounded
        +-- web_fetch           GET-only
        +-- knowledge_query     搜索 OKF 知识库

roxy monitor run
  |
  +-- feeds                     RSS / custom source
  +-- topics                    saved research topics
  +-- channels                  rss / arxiv / pubmed / wechat / agent_reach_web
  +-- run history               每次采集可追踪

roxy knowledge
  |
  +-- OKF JSONL                 import / export / validate
  +-- SQLite + FTS5             本地全文搜索
  +-- dedup                     URL + hash 去重

roxy eval
  |
  +-- traces                    脱敏交互记录
  +-- seeds                     评估样本
  +-- run/report/propose        基线、报告、建议
  +-- compare                   提升和退化对比
```

## 命令速查

```bash
roxy                          # 默认进入 TUI
roxy init [--yes]             # 初始化
roxy doctor [--json]          # 健康检查
roxy config set/get/list      # 配置管理
roxy chat [--no-tui]          # TUI 或纯文本 REPL

roxy knowledge search <query>
roxy knowledge stats
roxy knowledge export --out kb.jsonl
roxy knowledge import kb.jsonl
roxy knowledge validate kb.jsonl
roxy knowledge schema

roxy research feeds add/remove/list/status/enable/disable
roxy research topics add/remove/list
roxy research channels list/doctor
roxy research collect [--url | --all | --topics]
roxy research digest [--days | --run | --group-by | --out | --json]
roxy research runs list/latest/show

roxy monitor run [--json | --feeds-only | --topics-only]

roxy traces list/show/export
roxy eval seeds generate
roxy eval run/report/propose/compare

roxy dev check [--quick]
```

## 安全边界

Roxy 默认把能力放进明确边界里：

| 机制 | 说明 |
|------|------|
| Workspace sandbox | bounded 工具不能读取工作区外文件 |
| Risk level | `safe < caution < dangerous < blocked` |
| Approval gate | 需要审批的工具不会静默执行 |
| Secret masking | config、doctor、trace、log 中遮蔽 API key |
| No auto-apply | 自进化建议只生成 proposal，不自动改代码 |
| External adapters | wechat-query / Agent-Reach 通过外部协议接入，不 import 源码 |

## 配置

配置优先级：

```text
CLI 参数 > 环境变量 > ~/.roxy/config.yaml > 默认值
```

常用配置：

| 配置项 | 说明 |
|--------|------|
| `models.default` | 默认模型 |
| `models.providers.<name>.api_key` | provider API key |
| `research.feeds` | RSS/feed sources |
| `research.topics_data` | saved research topics |
| `research.wechat.db_path` | wechat-query SQLite 路径 |
| `ROXY_HOME` | 隔离运行时目录 |

Roxy 会自动检测常见环境变量，例如 `OPENAI_API_KEY`、`DEEPSEEK_API_KEY`、`ANTHROPIC_API_KEY`。

## 开发

```bash
pip install -e ".[dev]"
python -m pytest tests/
python -m roxy dev check
bash scripts/demo.sh
```

当前测试规模：`238 passed`。

## 路线图

| 版本 | 主题 |
|------|------|
| v0.1-v0.2 | Core Agent：CLI/TUI、工具、安全门、上下文压缩 |
| v0.3 | Research Workbench：知识库、RSS/ArXiv/PubMed、摘要、OKF |
| v0.4 | External Capability Layer：频道协议、学术频道、研究方向、统一监控 |
| v0.5 | Controlled Evolution：trace、eval、proposal、compare |
| v0.6 | Release Hardening：文档、dev check、版本一致性、发布清单 |

详见 [docs/FORMAL_VERSION_PLAN.md](docs/FORMAL_VERSION_PLAN.md)。

## License

MIT © [IBN-Spring](https://github.com/IBN-Spring)
