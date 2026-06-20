# Roxy Formal Version Plan

## 目的

Roxy 的 MVP 已经验证了核心闭环：TUI Agent、工具调用、安全门、上下文压缩、RSS/微信采集、知识库、摘要和 monitor。正式版本的目标不是继续堆功能，而是把 Roxy 从“可用原型”推进到“可长期使用、可发布、可扩展、可维护”的垂直领域自主调研 Agent。

正式版要达成三个核心结果：

1. **像 Claude Code / Hermes 一样可日常使用**
   - 有稳定 CLI/TUI 入口。
   - 有清晰初始化流程。
   - 有可恢复 session、工具调用展示、上下文压缩和错误恢复。
   - 用户不需要理解内部模块，也能完成初始化、采集、查询和对话。

2. **像 Agent-Reach 一样具备能力层架构**
   - 外部来源、工具、模型、通知渠道都以 channel/tool/provider/adapter 接入。
   - 每个能力都有 doctor 检查、配置入口、失败提示和降级策略。
   - Roxy core 不和 wechat-query、Agent-Reach、未来通信平台强耦合。

3. **像个人研究助理一样沉淀知识**
   - 支持长期监控信息源。
   - 自动去重、入库、搜索、摘要。
   - 能在聊天中调用知识库和网页工具。
   - 后续可以加入领域模板、生信工作流和受控自进化。

## 地图

### 1. 产品化初始化

把 `roxy init` 做成正式 bootstrapper，而不是简单问答配置。

需要完成：

- 支持交互式初始化和 `--yes` 非交互初始化。
- 创建 `~/.roxy/`、`sessions/`、`knowledge/roxy.db`。
- 配置 user profile、workspace、默认模型、RSS 源、wechat-query DB 路径。
- 初始化后自动给出下一步命令。
- 支持 `ROXY_HOME`，方便测试、服务器和多实例部署。
- doctor 能明确告诉用户哪些能力可用、哪些缺配置、怎么修。

### 2. TUI 正式化

把当前 TUI 从“能聊天”打磨成正式 agent CLI 体验。

需要完成：

- 首屏欢迎框：版本号、模型、workspace、session、getting started tips。
- Roxy mascot 状态接入：idle、thinking、typing、tool、success、error。
- 工具调用实时展示，而不是结束后才汇总。
- 支持 `/help`、`/clear`、`/sessions`、`/model`、`/doctor` 这类 slash commands。
- 支持 session resume/list/delete 的 TUI 入口。
- 支持无 API key 时的友好提示和配置引导。

### 3. Agent Runtime 硬化

让 QueryEngine 从“能跑”变成“可靠”。

需要完成：

- 把 `_call_with_tools` 收敛进 `ModelProvider.complete_with_tools()`。
- 统一 ProviderError、ToolError、PermissionError 的结构。
- 工具调用 loop 支持更清晰的 trace。
- 工具结果进入 session 前保持协议合法，避免 orphan tool messages。
- 增加 max runtime、max tool calls、max output chars。
- 为未来 sub-agent 预留 budget、depth、cancel 机制。

### 4. Knowledge Store 正式化

当前知识库已经可用，正式版要补长期使用能力。

需要完成：

- 完善 OKF v0.1 JSONL import/export。
- 增加 source、topic、tag、collection log 的 CLI/TUI 查看入口。
- 支持删除、重建索引、去重报告。
- 搜索支持 FTS query fallback，避免用户输入特殊字符导致 FTS 报错。
- 摘要 digest 支持按 source/topic/tag 分组。
- 预留 vector search，但不在正式版第一阶段强上。

### 5. Research Channels

把来源采集做成稳定能力层。

正式版第一阶段：

- RSS channel 稳定化。
- Wechat channel 保持外部 adapter，只读 wechat-query SQLite。
- Web fetch tool 保持 GET-only。
- Feed source manager 支持 enabled/disabled、last_run、last_error。
- monitor 支持 JSON 输出、非零 exit code、cron 友好。

正式版后续阶段：

- Agent-Reach adapter：复用其 channel/doctor 思路或作为外部命令依赖。
- ArXiv / PubMed / GitHub release / web search channel。
- 飞书/企业微信 webhook 通知。
- 普通微信、QQ 等高风险通信平台后置，不进入首个正式版核心。

### 6. 安全与权限

Roxy 后续会越来越有行动能力，安全策略必须保持在功能前面。

需要完成：

- workspace-bounded 工具默认不能越界。
- file_write、bash、sub-agent 进入前必须有 approval UI。
- blocked risk 永久拒绝。
- 所有 secrets 在 config、doctor、TUI、logs 中必须 mask。
- wechat-query DB 只读连接。
- monitor/log 不输出 API key、cookie、token。

### 7. 自进化与评估

自进化不进入正式版第一阶段核心能力，只保留架构位。

后续方向：

- 记录 trace：user input、tool calls、errors、final response。
- 从失败 trace 生成 eval case。
- 优化 prompt / skill / tool description。
- 所有 evolution 结果必须生成 diff，经过测试和人工确认后生效。
- 不允许自动覆盖核心代码。

### 8. 发布与工程化

正式版必须能被别人安装、运行、验证。

需要完成：

- README 快速上手完整。
- `scripts/demo.sh` 或 Windows 等价脚本可端到端演示。
- pyproject 依赖完整。
- 测试稳定，避免依赖用户真实 `~/.roxy`。
- CI 命令明确：`python -m pytest tests/`。
- release checklist：测试、doctor、demo、README、版本号。

## 验收标准

### A. 初始化验收

- `roxy init` 能交互式完成用户画像、模型、workspace、信息源配置。
- `roxy init --yes` 能非交互创建完整 runtime。
- 初始化后存在：
  - `~/.roxy/config.yaml`
  - `~/.roxy/sessions/`
  - `~/.roxy/knowledge/roxy.db`
- `ROXY_HOME=<path> roxy init --yes` 能在指定目录初始化。
- 初始化完成后运行 `roxy doctor` 有明确结果和下一步建议。

### B. TUI 验收

- `roxy chat` 启动后显示正式欢迎框。
- 欢迎框包含：
  - Roxy 名称
  - 版本号
  - 当前模型
  - session id
  - workspace
  - getting started tips
- 用户发消息后能看到 user/assistant 消息。
- 工具调用时 TUI 能显示调用状态和结果。
- 无 API key 时 TUI 显示可理解错误，不污染 session。
- `roxy chat --no-tui` 仍可作为 fallback 使用。

### C. Agent 能力验收

- Agent 能在聊天中调用：
  - `file_read`
  - `web_fetch`
  - `knowledge_query`
- 工具调用经过 PermissionManager。
- 超过 max tool iterations 会停止并提示。
- 工具结果进入上下文前会 micro-compact。
- 大上下文触发 auto-compact，失败三次后熔断。
- auto-compact 不会切断 assistant tool_calls / tool result 消息对。

### D. Research 闭环验收

- `roxy research feeds add/list/remove` 正常。
- `roxy research collect --url <rss>` 能采集 RSS 入库。
- `roxy research collect --all` 能采集全部 enabled feeds。
- `roxy research collect --channel wechat` 不要求 URL，并从配置的 wechat-query DB 只读采集。
- `roxy knowledge search <query>` 能搜到采集内容。
- `roxy research digest --days 7` 能生成摘要。
- `roxy monitor run --json` 无 feed 时优雅返回，有错误时 exit code 为 1。

### E. 安全验收

- `file_read` 不能读取 workspace 外文件。
- workspace escape、绝对路径越界、blocked path 都被拒绝。
- `requires_approval=True` 的工具在没有 approval UI 前不会执行。
- WeChat DB 使用只读 SQLite 连接。
- doctor/config/list/TUI 不泄露 API key。

### F. 工程质量验收

- `python -m pytest tests/` 全绿。
- `python -m roxy --version` 正常。
- `python -m roxy doctor --json` 输出完整 provider/tools/channels 状态。
- README 中的 Quick Start 可以按顺序跑通。
- demo 脚本不包含不存在的参数。
- 所有新增功能有最小测试覆盖。

## 正式版阶段建议

### v0.2 — Productized MVP

目标：把当前 MVP 打磨成可日常使用版本。

范围：

- init bootstrapper
- TUI 欢迎框和 mascot 状态
- doctor channels + KB 状态
- demo 脚本
- README 完整
- 工具调用和上下文压缩硬化

### v0.3 — Research Workbench

目标：让 Roxy 成为真正的研究信息工作台。

范围：

- source last_run / last_error
- digest 分组增强
- web/RSS/WeChat 采集体验增强
- slash commands
- session management TUI
- import/export OKF JSONL

### v0.4 — External Capability Layer

目标：接入更丰富外部能力，但保持 core 干净。

范围：

- Agent-Reach adapter
- ArXiv / PubMed / GitHub channel
- notification adapter
- provider routing
- channel doctor repair hints

### v0.5 — Controlled Evolution

目标：引入受控自进化。

范围：

- trace store
- eval generation
- prompt/tool description optimizer
- diff + tests + human review
- 不自动修改核心代码

## 当前优先级

下一步优先做：

1. 完成并提交 init bootstrapper。
2. 完成并提交 TUI 欢迎框和 mascot 状态接入。
3. doctor 增加 KB 状态、runtime home、sessions 状态。
4. 给 README 增加正式版路线和初始化说明。
5. 跑一次完整 demo，修掉真实使用里的摩擦点。
