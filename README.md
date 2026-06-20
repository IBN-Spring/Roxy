# Roxy

**Vertical-domain autonomous research Agent CLI/TUI.**

Roxy helps researchers gather, organize, and understand information.
It monitors RSS feeds and WeChat public accounts, stores findings in a
local knowledge base, and answers questions using LLM-powered chat —
all from the terminal.

## Architecture

```
roxy chat                    # Textual TUI — your AI research assistant
    │
    ├── QueryEngine          # Multi-turn agent loop with tool calling
    │   ├── file_read        #   Read files (workspace-bounded)
    │   ├── web_fetch        #   Fetch web pages (read-only)
    │   └── knowledge_query  #   Search your personal KB
    │
    ├── ContextCompactor     # Three-layer compression (micro → auto → memory)
    │   └── Circuit breaker  #   Stops retrying after 3 consecutive failures
    │
    └── Safety
        ├── Workspace sandbox   #   Bounded tools can't escape workspace
        ├── Risk levels         #   safe < caution < dangerous < blocked
        └── Approval gate       #   requires_approval enforced by ToolExecutor

roxy research collect --all  # Gather from all your configured sources
    │
    ├── RSSChannel            #   feedparser-based RSS/Atom reader
    ├── WechatChannel         #   Reads wechat-query SQLite (external, read-only)
    └── KnowledgeWriter       #   Dedup by URL hash + content hash → SQLite FTS5

roxy knowledge search "..."  # Query your personal research database
roxy research digest --days 7  # Summarize recent findings
roxy monitor run --json        # Cron-friendly one-shot collection
```

## Quick Start

### 1. Install

```bash
git clone https://github.com/IBN-Spring/Roxy.git
cd Roxy
pip install -e ".[tui]"
```

### 2. Bootstrap

```bash
# Interactive wizard
roxy init

# Or non-interactive (scripts / CI / servers)
roxy init --yes \
  --name "Your Name" \
  --domain "bioinformatics" \
  --topic "single-cell" \
  --topic "drug-design" \
  --feed "Hacker News=https://hnrss.org/frontpage" \
  --feed "ArXiv ML=http://export.arxiv.org/rss/cs.LG" \
  --skip-provider

# Use ROXY_HOME for isolated deployments
ROXY_HOME=/tmp/roxy-test roxy init --yes --skip-provider
```

### 3. Configure a model provider

```bash
roxy config set models.providers.openai.api_key "sk-..."
roxy config set models.default "openai/gpt-4.1-mini"

# Or via environment variables
export ROXY_MODELS_PROVIDERS_OPENAI_API_KEY="sk-..."
```

### 4. Start

```bash
roxy chat             # Textual TUI
roxy chat --no-tui    # Plain REPL
roxy doctor           # Health check
```

## Research Workflow

```bash
# Add information sources
roxy research feeds add "Hacker News" "https://hnrss.org/frontpage"
roxy research feeds list

# Collect from all enabled feeds
roxy research collect --all

# Search your knowledge base
roxy knowledge search "transformer architecture"
roxy knowledge stats

# Generate a digest of recent findings
roxy research digest --days 7
roxy research digest --json --days 3

# Ask Roxy about your research in chat
roxy chat
> "What have I collected about protein folding this week?"
```

## WeChat Integration

Roxy integrates with [wechat-query](https://github.com/) as an **external service**.
It reads the SQLite database that wechat-query produces — no source dependency.

```bash
roxy config set research.wechat.db_path "~/wechat-query/data/rss.db"
roxy research collect --channel wechat
roxy research collect --channel wechat --since "2025-06-01"
```

The connection is **read-only** (`mode=ro`) — Roxy cannot modify your wechat-query database.

## Scheduled Monitoring

```bash
# One-shot collection
roxy monitor run

# Cron-friendly JSON output (exit code 1 on errors)
roxy monitor run --json

# Cron example — every 6 hours
# 0 */6 * * * roxy monitor run --json >> ~/.roxy/monitor.log
```

## Commands

| Command | Description |
|---------|-------------|
| `roxy` | Launch TUI chat (default) |
| `roxy init` | Bootstrap setup (interactive or `--yes`) |
| `roxy doctor` | Health check — config, providers, tools, channels |
| `roxy chat` | Interactive TUI (`--no-tui` for REPL) |
| `roxy config set/get/list/path` | Manage configuration |
| `roxy knowledge search <query>` | Full-text search KB |
| `roxy knowledge stats` | KB statistics |
| `roxy research feeds add/remove/list` | Manage RSS sources |
| `roxy research collect [--url \| --all]` | Collect from feeds |
| `roxy research digest [--days \| --json]` | Research digest |
| `roxy monitor run [--json]` | One-shot collection |
| `python -m roxy <cmd>` | Alternative if `roxy` isn't on PATH |

## Configuration

**Priority**: CLI flags > environment variables > `~/.roxy/config.yaml` > defaults

| Key | Env Var | Description |
|-----|---------|-------------|
| `models.default` | `ROXY_MODELS_DEFAULT` | Default model (`provider/model`) |
| `models.providers.<name>.api_key` | `ROXY_MODELS_PROVIDERS_<NAME>_API_KEY` | Provider API key |
| `user.name` | `ROXY_USER_NAME` | Display name |
| `user.research_domain` | `ROXY_USER_RESEARCH_DOMAIN` | Research field |
| `user.topics` | `ROXY_USER_TOPICS` | Comma-separated research topics |
| `workspace.path` | `ROXY_WORKSPACE_PATH` | Workspace directory |
| `research.feeds` | — | List of `{name, url, enabled}` feed objects |
| `research.wechat.db_path` | — | Path to wechat-query `rss.db` |
| `ROXY_HOME` | — | Override `~/.roxy` directory (for testing/isolation) |

## Safety

- **Workspace-bounded**: `file_read` cannot access files outside the workspace
- **Risk levels**: `safe` < `caution` < `dangerous` < `blocked`
- **Approval gate**: `requires_approval` enforced by `ToolExecutor` — caution+ tools don't run silently
- **Read-only wechat**: WeChat DB opened with `mode=ro` URI
- **Circuit breaker**: Auto-compact stops retrying after 3 consecutive failures
- **No file write, no shell, no recursive sub-agents** — safety-first design

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/          # 180+ tests
python -m roxy --version
python -m roxy doctor --json
bash scripts/demo.sh             # End-to-end smoke test
```

## Roadmap

| Version | Theme | Highlights |
|---------|-------|------------|
| **v0.1** (current) | Core MVP | TUI chat, 3 tools, RSS/WeChat channels, KB + FTS5, compaction, safety gates |
| **v0.2** | Productized MVP | TUI welcome + mascot, doctor KB/sessions, slash commands, session management |
| **v0.3** | Research Workbench | Source last_run/last_error, digest grouping, OKF import/export, FTS fallback |
| **v0.4** | External Capability | Agent-Reach adapter, ArXiv/PubMed channels, webhook notifications, provider routing |
| **v0.5** | Controlled Evolution | Trace store, eval generation, prompt optimizer, human-reviewed diffs |

See [docs/FORMAL_VERSION_PLAN.md](docs/FORMAL_VERSION_PLAN.md) for detailed requirements and acceptance criteria.

## License

MIT
