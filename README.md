<div align="center">
<img src="assets/mascot/roxy-readme-mascot.png" alt="Roxy Mascot" width="200"/>

# Roxy

**垂直领域自主调研 Agent · Vertical-domain Autonomous Research Agent**

<p>
  <a href="https://github.com/IBN-Spring/Roxy/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="#"><img src="https://img.shields.io/badge/version-0.6.0-green.svg" alt="Version 0.6.0"></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-238%20passed-brightgreen.svg" alt="238 Tests"></a>
  <a href="docs/FORMAL_VERSION_PLAN.md"><img src="https://img.shields.io/badge/roadmap-v0.1--v0.6-orange.svg" alt="Roadmap"></a>
</p>

<p>
  <b>English</b> | <a href="README_zh.md">中文</a>
</p>
</div>

---

Roxy is a research agent that monitors information sources, builds a knowledge base, and answers
questions — all from the terminal. It speaks to RSS feeds, ArXiv, PubMed, and WeChat, stores
findings in a portable knowledge format, and lets you chat with your research via a TUI.

<div align="center"><img src="assets/mascot/roxy-mage-preview.gif" width="120"/></div>

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Features](#features)
- [Research Workflow](#research-workflow)
- [TUI Slash Commands](#tui-slash-commands)
- [Channels](#channels)
- [Knowledge Format (OKF)](#knowledge-format-okf)
- [Controlled Evolution](#controlled-evolution)
- [Commands](#commands)
- [Configuration](#configuration)
- [Safety](#safety)
- [Development](#development)
- [Roadmap](#roadmap)
- [License](#license)

## Quick Start

```bash
# Install
git clone https://github.com/IBN-Spring/Roxy.git
cd Roxy
pip install -e ".[tui]"

# Bootstrap
roxy init --yes --name "Your Name" --domain "bioinformatics"

# Configure a model
roxy config set models.providers.deepseek.api_key "sk-..."

# Launch
roxy chat
```

Or with environment variables:
```bash
export DEEPSEEK_API_KEY="sk-..."
roxy chat
```

## Architecture

<div align="center">
<img src="assets/mascot/roxy-mage-sprite-sheet.png" alt="Roxy States" width="360"/>
</div>

```
roxy chat                     # Textual TUI — AI research workbench
  │
  ├── /status /feeds /collect /runs /digest /kb /topics
  ├── QueryEngine              # Multi-turn agent loop with tool calling
  │   ├── file_read            # Workspace-bounded file reader
  │   ├── web_fetch            # GET-only web page fetcher
  │   └── knowledge_query      # Search personal knowledge base
  ├── ContextCompactor         # Micro-compact + auto-compact + circuit breaker
  └── Safety                   # Permission system + risk levels + workspace sandbox

roxy monitor run               # Unified collection — feeds + topics
  ├── RSSChannel               # Any RSS/Atom feed (feedparser)
  ├── ArXivChannel             # Academic papers (free API, no key)
  ├── PubMedChannel            # NCBI papers (free API, no key)
  ├── WechatChannel            # External wechat-query SQLite (read-only adapter)
  └── AgentReachWebChannel     # External CLI bridge (Agent-Reach adapter)

roxy knowledge                 # OKF v0.1 knowledge base
  ├── SQLite + FTS5            # Runtime store
  ├── JSONL export/import      # Portable interchange
  └── Schema validator         # Strict OKF compliance

roxy eval                      # Controlled evolution harness
  ├── seeds generate           # Extract eval cases from traces
  ├── eval run                 # Baseline evaluation (mock or live)
  ├── eval propose             # Improvement suggestions (no auto-apply)
  └── eval compare             # Side-by-side version diff
```

## Features

| Category | Feature | Description |
|----------|---------|-------------|
| **Agent** | TUI + REPL | Textual chat with streaming, slash commands, session resume |
| | Tool calling | file_read, web_fetch, knowledge_query with permission gating |
| | Context compaction | Micro-compact (per-turn) + auto-compact (LLM summary) + circuit breaker |
| **Research** | 5 channels | RSS, ArXiv, PubMed, WeChat (adapter), Agent-Reach (adapter) |
| | Source management | Feed state tracking, enable/disable, last_run/last_error |
| | Topics | Saved research queries with multi-channel collection |
| | Digest | Structured markdown reports grouped by source/date/tag |
| | Run history | Collection run tracking with per-feed metrics |
| **Knowledge** | OKF v0.1 | Portable JSONL format with JSON Schema validation |
| | FTS5 search | Full-text search with tag/source/date filters |
| | Import/Export | JSONL roundtrip with dedup and validation |
| **Evolution** | Trace store | Privacy-safe recording of every agent turn |
| | Eval harness | Mock/live eval runner with baseline reports |
| | Proposal generator | Failure analysis with improvement suggestions |
| | Harness compare | Side-by-side version diff with regression detection |
| **Safety** | Risk levels | safe < caution < dangerous < blocked |
| | Workspace sandbox | Bounded tools cannot escape workspace |
| | Approval gate | requires_approval enforced by ToolExecutor |
| | Secrets masking | API keys masked in config, doctor, traces, logs |
| **DevOps** | ROXY_HOME | Isolated runtime directory for testing/CI |
| | `roxy dev check` | Release readiness checks |
| | Cron-friendly | `roxy monitor run --json` with structured exit codes |

## Research Workflow

```bash
# 1. Add information sources
roxy research feeds add "Hacker News" "https://hnrss.org/frontpage"

# 2. Save research topics for continuous monitoring
roxy research topics add "single cell RNA-seq" --channels arxiv,pubmed

# 3. One command to collect everything
roxy monitor run

# 4. Search, digest, export
roxy knowledge search "transformer"
roxy research digest --days 7 --out weekly.md
roxy knowledge export --out kb.jsonl
roxy knowledge import kb.jsonl
```

Or entirely within the TUI:
```
/collect           # Collect from feeds + topics
/runs              # View recent runs
/digest            # 7-day summary
/kb transformer    # Search knowledge base
/feeds             # Check source status
/topics            # Check topic status
```

## TUI Slash Commands

| Command | Action |
|---------|--------|
| `/help` | Show all commands |
| `/status` | Master overview (model, feeds, KB, channels, last run) |
| `/doctor` | Provider / tools / channels / KB status |
| `/model` | Show or switch current model |
| `/key` | API key status and configuration |
| `/feeds` | Feed source status |
| `/collect` | Collect from all enabled feeds |
| `/collect topics` | Collect from all saved research topics |
| `/runs` | Recent collection runs |
| `/digest [N\|latest\|<id>]` | Research digest summary |
| `/kb <query>` | Search knowledge base |
| `/topics` | Saved research topics |
| `/sessions` | List recent sessions |
| `/resume <id>` | Resume a session |
| `/clear` | Clear screen (session kept) |
| `/exit` | Quit |

## Channels

| Channel | Tier | Config | Description |
|---------|------|--------|-------------|
| `rss` | 0 · Ready | None | Any RSS/Atom feed |
| `arxiv` | 0 · Ready | None | ArXiv papers (free API) |
| `pubmed` | 0 · Ready | None | PubMed/NCBI papers (free API) |
| `wechat` | 1 · Config | `research.wechat.db_path` | WeChat articles via wechat-query |
| `agent_reach_web` | 1 · External | `agent-reach` CLI on PATH | Web reading via Agent-Reach |

```bash
roxy research channels list           # Table view
roxy research channels doctor         # Health check + repair hints
roxy research collect --channel arxiv --topic "LLM reasoning" --max-items 5
```

## Knowledge Format (OKF v0.1)

Roxy uses the **Open Knowledge Format** — a portable JSONL schema for knowledge interchange.

```json
{
  "okf_version": "0.1",
  "id": "a1b2c3d4e5f6",
  "type": "item",
  "title": "Attention Is All You Need",
  "canonical_url": "https://arxiv.org/abs/1706.03762",
  "content_md": "...",
  "authors": ["Vaswani", "Shazeer", "Parmar"],
  "published_at": "2017-06-12",
  "collected_via": "arxiv",
  "source": {"type": "paper", "channel_name": "ArXiv"},
  "tags": ["transformer", "attention"]
}
```

```bash
roxy knowledge export --out kb.jsonl
roxy knowledge import kb.jsonl
roxy knowledge validate kb.jsonl
roxy knowledge schema
```

## Controlled Evolution

Roxy records its behavior, generates eval cases, and proposes improvements —
but **never applies them automatically**.

```
trace → seed → run → report → propose → compare → review → apply
                                                      ↑
                                              human decides
```

```bash
# Record traces (automatic during chat)
# Generate eval seeds
roxy eval seeds generate --out seeds.jsonl

# Baseline evaluation
roxy eval run seeds.jsonl --out baseline.json

# Generate improvement proposals
roxy eval propose baseline.json --out proposals.md

# After manual changes, compare
roxy eval run seeds.jsonl --out candidate.json
roxy eval compare baseline.json candidate.json
```

## Commands

```
roxy                          # TUI chat (default)
roxy init [--yes]             # Bootstrap setup
roxy doctor                   # Health check
roxy config set/get/list      # Configuration
roxy chat [--no-tui]          # Chat (TUI or REPL)

roxy knowledge search <query> # Full-text search
roxy knowledge stats          # KB statistics
roxy knowledge export/import  # OKF JSONL import/export
roxy knowledge validate       # Validate JSONL file
roxy knowledge schema         # Show OKF JSON Schema

roxy research feeds add/remove/list/status/enable/disable
roxy research topics add/remove/list
roxy research channels list/doctor
roxy research collect [--url|--all|--topics]
roxy research digest [--days|--run|--group-by|--out|--json]
roxy research runs list/latest/show

roxy monitor run [--json|--feeds-only|--topics-only]

roxy traces list/show/export
roxy eval seeds generate
roxy eval run <cases> [--live|--out]
roxy eval report <report>
roxy eval propose <report> [--out|--target]
roxy eval compare <baseline> <candidate>

roxy dev check [--quick]      # Release readiness
```

## Configuration

Priority: CLI flags > environment variables > `~/.roxy/config.yaml` > defaults

| Key | Env Var | Description |
|-----|---------|-------------|
| `models.default` | `ROXY_MODELS_DEFAULT` | Default model (`provider/model`) |
| `models.providers.<name>.api_key` | `ROXY_MODELS_PROVIDERS_<NAME>_API_KEY` | Provider API key |
| `research.feeds` | — | List of `{name, url, enabled}` feed objects |
| `research.topics_data` | — | List of saved research topics |
| `research.wechat.db_path` | — | Path to wechat-query `rss.db` |
| `ROXY_HOME` | — | Override `~/.roxy` directory |

Well-known env vars detected automatically: `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, etc.

## Safety

- **Workspace-bounded**: `file_read` cannot access files outside the workspace
- **Risk levels**: `safe` < `caution` < `dangerous` < `blocked`
- **Approval gate**: `requires_approval` enforced by `ToolExecutor`
- **Read-only adapters**: WeChat DB opened with `mode=ro` URI
- **Circuit breaker**: Auto-compact stops after 3 consecutive failures
- **Secrets masking**: API keys masked in config, doctor, TUI, traces, logs
- **No auto-apply**: Evolution proposals are markdown files — never auto-applied

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/          # 238 tests
python -m roxy dev check          # Release health check
bash scripts/demo.sh              # End-to-end smoke
```

## Roadmap

| Version | Theme | Highlights |
|---------|-------|------------|
| **v0.1–0.2** | Core Agent | TUI chat, tools, safety gates, context compaction |
| **v0.3** | Research Workbench | KB + FTS5, RSS/ArXiv/PubMed, digest, run history, OKF |
| **v0.4** | External Capability | Channel contract, academic channels, topics, unified monitor |
| **v0.5** | Controlled Evolution | Trace store, eval harness, proposals, compare (no auto-apply) |
| **v0.6** | Release Hardening | Versioning, dev check, docs, release checklist |

See [docs/FORMAL_VERSION_PLAN.md](docs/FORMAL_VERSION_PLAN.md) for detailed requirements.

## License

MIT © [IBN-Spring](https://github.com/IBN-Spring)

---

<div align="center">
  <sub>Built with ❤️ by Roxy contributors</sub>
</div>
