# Strands in Action · 系列总体规划（v1）

> **事实基线**：见 [`docs/00-facts-baseline.md`](docs/00-facts-baseline.md)，抓取于 2026-10-21。
> 写文章只允许用那份文件里的事实，或跑出来的数字。**没有跑出来的数字不进文章。**
>
> **方法沿用 `bedrock-agentcore-in-action` 的 v3**：独立用例 + 难度阶梯 + 覆盖矩阵 +
> 真机实测 + 英文稿。**字数规则 2026-11-01 起改为内容优先**（区间只是默认起点，句级纪律不放松，
> 见 §6）。三个已拍板决策（2026-10-21）：
>
> | # | 决策 | 结论 |
> |---|---|---|
> | A | 系列规模 | **8 篇完整阶梯**（D1→D5）+ 1 篇概览 |
> | B | 首发篇 | **UC01 · The Loop** |
> | C | 仓库组织 | **新建独立仓库 `strands-in-action`**，与 AgentCore 系列双向 cross-link |

---

## 1. 系列一句话

> **AgentCore 系列讲的是"云替你扛的那 14 件事"；这个系列讲的是"你自己写代码掌控的那
> 一层"。** Strands 是 SDK，不是平台 —— 这是它和 AgentCore 的分界线，也是整个系列的立论。

官方原话锚点（写入概览篇）：

> "What Strands deliberately does not add is a platform. It runs in your own process as a
> library, with no hosted control plane."

## 2. 难度阶梯（沿用 AgentCore 的刻度尺）

| 难度 | 新增能力 | 参考耗时 | 读者要理解的机制 |
|:--:|---|---|---|
| D1 | 1–2 | ≤ 30 min | agent 跑在哪、一次调用是什么 |
| D2 | 1–2 | ≈ 1 h | 工具的契约、执行的边界 |
| D3 | 2–3 | ≈ 2 h | 状态与隔离维度 |
| D4 | 3–5 | 3–4 h | 编排、评测 |
| D5 | 5+ | ≈ 4 h | 部署、上线 |

## 3. 八个用例（D1→D5，序列单调不减）

| # | 用例 | D | 深挖 | 一句话场景 | 文章角度（张力来源） |
|---|---|:--:|---|---|---|
| 01 | **The Loop** ✅ | D1 | agent loop / trace / token 用量 | 四行代码跑起来一个 agent | 循环不在 `Agent` 里；是递归不是 `while`；13 种 stop_reason 只有 1 种继续 |
| 02 | **Tools & MCP** | D2 | `@tool`、schema、MCP、vended_tools 迁移 | 给 agent 一个计算器、一个读文件、一个 MCP 工具 | docstring 就是 API 契约；24 个内置工具正在被废弃 |
| 03 | **Execution Limits** | D2 | limits / tool quota / token budget / cancel | 一个会失控的 agent，被四个边界拦住 | 生产事故不是模型变笨，是没设边界；四个维度一个都不能少 |
| 04 | **Sessions, State & Memory** | D3 | SnapshotSessionManager / File / S3 / AgentCore Memory、conversation manager、agent.state | 重启后它还认识你 | "记忆"不是一件事，是会话、状态、长期记忆三件事 |
| 05 | **Multi-Agent 四选一** | D4 | Swarm / Graph / Workflow / A2A | 同一个任务，四种编排，四种 trace | 四种范式不是难易度排序，是四种不同的放弃 |
| 06 | **Guardrails + HITL** | D4 | guardrail_intervened、interrupt/resume、HumanInTheLoop | 让它别乱说，关键处停下来问人 | 做裁决的东西不能是能被对话的东西（呼应 AgentCore UC04） |
| 07 | **Evals 闭环** | D4 | strands-agents-evals 13+ evaluator、LLM-as-judge、Experiment/Case | 上线两个月后它变差了，你凭什么知道 | "看着点"换成可度量（呼应 AgentCore UC06，但用 SDK 而非托管服务） |
| 08 | **Deploy 六选一** | D5 | AgentCore / Lambda / Fargate / App Runner / EKS / EC2 | 同一个 agent 部署到两个目标，行为一致 | SDK 不挑落脚点；选目标的决策树 |

**概览篇 A0**：`Strands in Action: 8 Independent Experiments, One SDK` ——
系列导航 + 与 AgentCore 的分界图。

> 难度序列 1,2,2,3,4,4,4,5 单调不减 ✓

**幕结构（2026-11-04 v2，替代原 Run/Control/Trust）**：

| 幕 | 篇 | 一句话 |
|---|---|---|
| **Principle 原理** | 01 | 循环本身怎么工作（源码级） |
| **Capability 能力** | 02 工具 / 03 边界 / 04 记忆 / 05 编排 | 让它能做更多事 |
| **Production 生产** | 06 护栏 / 07 评测 / 08 部署 | 敢让它上线的最后三道门 |

调整理由：UC01 定稿后 01 已是原理篇而非"跑起来"篇；04 记忆与 05 编排是能力不是控制/信任；
原 Trust 幕 4 篇性质混杂。难度序列不受影响。

**跨篇依赖规则（2026-11-04 新增）**：UC01 已讲透的内容，后续篇不得重讲，直接从新起点开讲，
且**每篇开头必须有一句指明"本文假设你读过 01 的哪节"**：

| 篇 | 新起点（UC01 已覆盖的前提） |
|---|---|
| 02 | 工具的 user 角色回传 + 5500 字符 schema 成本 → 从「docstring 即契约」开讲 |
| 03 | 13 种 stop_reason 四分法 → 从「如何主动制造 `limit_*` 终止」开讲 |
| 04 | 状态 = 一个消息列表、对话是唯一通道 → 从「这个列表怎么持久化」开讲 |
| 06 | `guardrail_intervened` 分组 + hook 否决模型调用（event_loop.py:657）→ 从「裁决者不能是对话参与者」开讲 |

## 4. 覆盖矩阵

● = 深挖　○ = 用到

| 能力 | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| agent loop / Agent API | ● | ● | ● | ● | ● | ● | ● | ● |
| model providers | ● | ○ | | ○ | ○ | ○ | ○ | ○ |
| trace / OTel / metrics | ● | ○ | ● | | ○ | ○ | ● | ● |
| `@tool` / schema | | ● | ○ | ○ | ○ | | | ○ |
| 内置工具 / vended_tools | | ● | | | ○ | | | |
| MCP | | ● | | | | | | ○ |
| limits / cancel | ○ | | ● | | ● | ● | | |
| session / state / memory | ○ | | | ● | ○ | | | ○ |
| conversation manager | | ○ | | ● | ○ | | | |
| Swarm / Graph / Workflow / A2A | | | ○ | | ● | | | |
| guardrails | | ○ | | | | ● | ○ | |
| interrupt / HITL | | ○ | | | | ● | | |
| structured output | ○ | ○ | | | ○ | | ● | |
| evals | | ○ | ○ | | | | ● | ○ |
| 部署目标 6 个 | | | | | | | | ● |
| hooks | ● | | ● | | ○ | ● | ○ | |

## 5. 与 AgentCore 系列的衔接（决策 C）

| | AgentCore 系列 | 本系列 |
|---|---|---|
| 仓库 | `bedrock-agentcore-in-action` | `strands-in-action` |
| 立场 | 托管服务的 14 项能力 | SDK 自己掌控的一层 |
| 互相引用 | UC01/UC05 指向 Strands 的 loop/工具篇；UC02 指向本系列 UC04 | UC04/UC08 回指 AgentCore 的 Memory/Runtime 篇 |

**strands-in-action 仓库结构**（镜像 AgentCore v3）：

```
strands-in-action/
├── README.md  PLAN.md  LICENSE  .gitignore
├── docs/
│   ├── 00-facts-baseline.md     # 已有
│   ├── 01-overview.md           # Strands 全景（英文）
│   ├── 02-capability-map.yaml   # 机器可读覆盖清单（CI 校验）
│   ├── 03-conventions.md
│   └── 99-troubleshooting.md
├── usecases/
│   ├── 01-the-loop/  …  08-deploy-six-targets/
│   │   ├── README.md  ARCHITECTURE.md  src/  evidence/  tests/smoke.py  article.md
├── shared/scripts/{bootstrap.sh, new-usecase.sh, verify-coverage.py}
└── .github/workflows/
```

> 与 AgentCore 差异：**没有 IaC 栈这一层**（Strands 前 7 篇本地就能跑，只有 UC08 部署篇
> 需要云资源）。所以独立性契约 I3（IaC 独立）改为 **I3': 每例一个自包含 Python 模块 +
> `uv` 依赖锁定**；标签三件套只在 UC08 需要。

## 6. 文章骨架（2026-11-04 v2：从固定 8 节改为必含元件清单）

固定节序不再强制。每篇必须含有以下元件，顺序按叙事需要排：

- **开篇**：一个能跑的最小用例 + 一个本文要回答的具体问题（禁止先讲排错/环境，见 UC01 v5 教训）
- **全景**：一张机制总图，读者先见全貌再看细节（如 UC01 的 F3 cycle 内部图）
- **源码**：核心机制引用 SDK 源码，每块带 `file:line`，3–8 行配一两句解读
- **why**：设计动机（为什么这样实现），推断须明确标注非官方声明
- **证据**：每个数字出自真实运行，evidence/ 留档
- `What surprised me` / `When not to use this` / `Try it yourself` / takeaways 收尾（不写下篇预告）

硬约束（沿用 `agentcore-use-case-article`，2026-11-04 修订）：**字数内容优先，1000–1300 词仅为
默认起点不是上限**（UC01 实际 2007 词），句级纪律（句长/连接词/被动/长句/名词化）不放松；
零 Markdown 表格；每个代码块带语言；正文无加粗（节内引导词除外）；无中文字符；
图片根路径 `/images/<slug>/`；账号 ID 脱敏 `123456789012`；
**代码用代码块、运行结果用图**（终端面板 SVG→2880 宽 PNG，见 `agentcore-figures`）。

## 7. 发布矩阵（沿用）

GitHub Pages（xiongpin.dev，单一真相源）→ Dev.to（主阵地，canonical 指回）→
Medium（@pinxiong.cn，人工）→ 副本 Hashnode → 社区 Hacker News / Lobsters / Reddit r/aws。
不做 LinkedIn / DZone / InfoQ。双周一篇。

## 8. 路线图

| 阶段 | 内容 | 完成标志 |
|---|---|---|
| P0 | 事实基线（done）、PLAN（done）、仓库骨架、生成器 | `new-usecase.sh` 生成空用例通过 CI |
| P1 | UC01 真机跑 + 文章 + 发布 | 文章已 v6 定稿（2007 词 / 34 代码块 / 7 图 / 终检 0），**待用户指令发布**；发布后 Dev.to + Medium + Pages 三处齐 |
| P2 | UC02 + UC03 | DoD 全绿 |
| P3 | UC04 + UC05 | 同上 |
| P4 | UC06 + UC07 + UC08 | 同上，UC08 两个部署目标实测 |
| P5 | A0 概览 + `make verify-all` 全绿 | 覆盖矩阵每项有实证 |

**每例 DoD（沿用，IaC 条款改为依赖锁定条款）**：干净环境跑通；`smoke.py` 断言全过；
十二节文档齐；每步有预期输出与失败修复；至少一张真实运行截图；`article.md` 初稿；
覆盖声明与 smoke 一致；难度声明与刻度一致且序列单调。

## 9. 风险

| 风险 | 对策 |
|---|---|
| SDK 发版极快（两周一个 minor） | 每篇顶部标 "verified on YYYY-MM-DD, sdk-python 1.61.1" |
| 内置工具层正在换血（24 deprecated） | UC02 显式讲迁移，文章生命周期内持续有效 |
| 本机 CLI 默认 `us-east-1` ≠ SDK 文档默认 `us-west-2`（2026-11-01 修正：此前误记为 ap-southeast-1） | 每条命令显式 `region_name`；UC01 已写成第一个坑，并教读者看 SDK 自打印的 `└ Bedrock region:` |
| 默认模型 `global.anthropic.claude-sonnet-4-6` 受 Anthropic 地理限制，**已实测失败** | **已解决**：UC01 改用 Bedrock 上的 `deepseek.v3.2`，一行 model id 完成替换 |
| Docker 未安装，UC08 的容器目标跑不了 | UC08 只实测 AgentCore + Lambda 两个无 Docker 目标，其余给决策树 |
