<div align="center">
<img src="assets/mascot/roxy-readme-mascot.png" alt="Roxy 吉祥物" width="200"/>

# Roxy

**垂直领域自主调研 Agent · Vertical-domain Autonomous Research Agent**

<p>
  <a href="https://github.com/IBN-Spring/Roxy/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="#"><img src="https://img.shields.io/badge/version-0.6.0-green.svg" alt="Version 0.6.0"></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-238%20passed-brightgreen.svg" alt="238 Tests"></a>
</p>

<p>
  <a href="README.md">English</a> | <b>中文</b>
</p>
</div>

---

Roxy 是一个终端里的研究助手：监控信息源、构建知识库、回答问题。
它连接 RSS、ArXiv、PubMed 和微信公众号，将发现存入可移植的知识格式，
并让你在 TUI 中与研究内容对话。

## 快速开始

```bash
git clone https://github.com/IBN-Spring/Roxy.git
cd Roxy
pip install -e ".[tui]"

roxy init --yes --name "你的名字" --domain "生物信息学"
roxy config set models.providers.deepseek.api_key "sk-..."
roxy chat
```

## 研究工作流

```bash
# 添加信息源
roxy research feeds add "机器之心" "https://jiqizhixin.com/rss"

# 保存研究方向
roxy research topics add "单细胞RNA-seq" --channels arxiv,pubmed

# 一键采集
roxy monitor run

# 搜索、摘要、导出
roxy knowledge search "transformer"
roxy research digest --days 7 --out weekly.md
```

## TUI 命令

`/help` `/status` `/doctor` `/model` `/key`
`/feeds` `/collect` `/runs` `/digest` `/kb` `/topics`
`/sessions` `/resume` `/clear` `/exit`

## 频道

| 频道 | 级别 | 说明 |
|------|------|------|
| `rss` | 0 · 就绪 | 任意 RSS/Atom 源 |
| `arxiv` | 0 · 就绪 | ArXiv 学术论文（免费 API） |
| `pubmed` | 0 · 就绪 | PubMed/NCBI 论文（免费 API） |
| `wechat` | 1 · 配置 | 微信公众号（通过 wechat-query） |
| `agent_reach_web` | 1 · 外部 | 网页读取（通过 Agent-Reach CLI） |

## 知识格式 (OKF v0.1)

```bash
roxy knowledge export --out kb.jsonl
roxy knowledge import kb.jsonl
roxy knowledge validate kb.jsonl
```

## 受控自进化

Roxy 记录行为、生成评估用例、提出改进建议——
但**绝不自动应用**。人来决定。

```
trace → seed → run → report → propose → compare → review → apply
                                                      ↑
                                               人类决定
```

## 安全

- 工作区隔离：`file_read` 无法读取工作区外文件
- 风险等级：safe < caution < dangerous < blocked
- 审批门：`requires_approval` 由 ToolExecutor 强制执行
- 密钥脱敏：config、doctor、TUI、traces、logs 均遮蔽 API key
- 无自动应用：进化建议仅输出 markdown，不修改代码

## 命令速查

```bash
roxy                          # TUI 对话（默认）
roxy init [--yes]             # 初始化
roxy doctor                   # 健康检查
roxy chat [--no-tui]          # 对话

roxy knowledge search <query> # 全文搜索
roxy research collect --all   # 采集全部源
roxy research digest --days 7 # 生成摘要
roxy monitor run --json       # 定时采集（cron 友好）
roxy eval run --live          # 评估运行
roxy dev check                # 发布检查
```

## 路线图

| 版本 | 主题 |
|------|------|
| v0.1–0.2 | 核心 Agent：TUI、工具、安全、压缩 |
| v0.3 | 研究工作台：知识库、RSS/ArXiv/PubMed、摘要、OKF |
| v0.4 | 外部能力层：频道协议、学术频道、研究方向、统一监控 |
| v0.5 | 受控自进化：轨迹记录、评估框架、改进建议（无自动应用） |
| v0.6 | 发布加固 |

## 许可证

MIT © [IBN-Spring](https://github.com/IBN-Spring)
