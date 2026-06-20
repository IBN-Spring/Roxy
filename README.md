# Roxy v0.6.0

**Vertical-domain autonomous research Agent CLI/TUI.**

Roxy monitors RSS feeds, academic sources (ArXiv/PubMed), and WeChat public accounts,
stores findings in a local knowledge base, and answers questions using LLM-powered chat —
all from the terminal.

## Quick Start

```bash
pip install -e ".[tui]"
roxy init --yes --name "Researcher" --skip-provider
roxy config set models.providers.deepseek.api_key "sk-..."
roxy chat
```

## Architecture

```
roxy chat                     # Textual TUI — AI research workbench
  ├── /status /feeds /collect /runs /digest /kb   # Research commands
  ├── QueryEngine              # Multi-turn agent loop with tool calling
  │   ├── file_read            # Workspace-bounded file reader
  │   ├── web_fetch            # GET-only web page fetcher
  │   └── knowledge_query      # Search personal knowledge base
  ├── Context compaction       # Auto-compress long conversations
  └── Safety gates             # Permission system + risk levels

roxy research collect --all    # Gather from all configured sources
  ├── RSS feeds                # Any RSS/Atom feed (feedparser)
  ├── ArXiv API                # Academic papers (free, no key)
  ├── PubMed API               # NCBI papers (free, no key)
  ├── WeChat (adapter)         # External wechat-query SQLite (read-only)
  └── Agent-Reach (adapter)    # External CLI bridge

roxy knowledge search "..."    # FTS5 full-text search
roxy research digest --out     # Structured markdown research reports
roxy eval run --live           # Controlled evolution harness
```

## Research Workflow

```bash
# 1. Add information sources
roxy research feeds add "Hacker News" "https://hnrss.org/frontpage"

# 2. Save research topics for continuous monitoring
roxy research topics add "single cell RNA-seq" --channels arxiv,pubmed

# 3. One command to collect everything
roxy monitor run
# or in TUI: /collect

# 4. Search, digest, export
roxy knowledge search "transformer"
roxy research digest --days 7 --out weekly.md
roxy knowledge export --out kb.jsonl
roxy knowledge import kb.jsonl
```

## TUI Slash Commands (20 total)

| Category | Commands |
|----------|----------|
| Chat | `/help` `/status` `/key` `/clear` `/doctor` `/model` `/exit` |
| Session | `/sessions` `/resume` |
| Research | `/feeds` `/collect` `/runs` `/digest` `/kb` `/topics` |

## Channels

| Channel | Tier | Status | Description |
|---------|------|--------|-------------|
| `rss` | 0 | Ready | Any RSS/Atom feed |
| `arxiv` | 0 | Ready | ArXiv academic papers (free API) |
| `pubmed` | 0 | Ready | PubMed/NCBI papers (free API) |
| `wechat` | 1 | Config | WeChat articles via wechat-query |
| `agent_reach_web` | 1 | External | Web reading via Agent-Reach CLI |

```bash
roxy research channels list
roxy research channels doctor
```

## Knowledge Format (OKF v0.1)

Portable JSONL format with strict schema validation:

```bash
roxy knowledge export --out kb.jsonl
roxy knowledge import kb.jsonl
roxy knowledge validate kb.jsonl
roxy knowledge schema
```

## Controlled Evolution

```bash
# Record agent behavior (automatic)
# Generate eval seeds from traces
roxy eval seeds generate --out seeds.jsonl

# Baseline evaluation
roxy eval run seeds.jsonl --out baseline.json

# Generate improvement proposals (no auto-apply)
roxy eval propose baseline.json --out proposals.md

# Compare two versions
roxy eval compare baseline.json candidate.json
```

Pipeline: `trace → seed → run → report → propose → compare → review → apply`

## Safety

- Workspace-bounded tools cannot escape workspace
- Risk levels: `safe` < `caution` < `dangerous` < `blocked`
- `requires_approval` enforced by ToolExecutor
- Auto-compact circuit breaker prevents runaway API costs
- WeChat DB read-only (`mode=ro`)
- Secrets masked in doctor, config, traces, logs

## Commands

```bash
roxy                        # TUI chat (default)
roxy init [--yes]           # Bootstrap setup
roxy doctor                 # Health check
roxy config set/get/list    # Configuration
roxy chat [--no-tui]        # Chat

roxy knowledge search/stats/export/import/validate/schema
roxy research feeds/collect/digest/runs/channels/topics
roxy monitor run [--json] [--feeds-only|--topics-only]
roxy traces list/show/export
roxy eval seeds/run/report/propose/compare
roxy dev check              # Release readiness
```

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/          # 238 tests
python -m roxy dev check          # Release checks
bash scripts/demo.sh              # End-to-end smoke
```

## Release Checklist

- [ ] `python -m pytest tests/` all pass
- [ ] `python -m roxy dev check` all pass
- [ ] `python -m roxy --version` correct
- [ ] `python -m roxy doctor --json` valid
- [ ] `bash scripts/demo.sh` no failures
- [ ] Fresh install: `ROXY_HOME=/tmp/roxy-fresh roxy init --yes --skip-provider`
- [ ] `roxy eval run` mock mode works
- [ ] README up to date
- [ ] `git tag v<VERSION>`

## License

MIT
