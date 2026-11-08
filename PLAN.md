# Strands in Action · 系列总体规划（v3，2026-11-08）

> **事实基线**：见 [`docs/00-facts-baseline.md`](docs/00-facts-baseline.md)。
> 写文章只允许用那份文件里的事实，或跑出来的数字。**没有跑出来的数字不进文章。**
>
> **v3 变更（用户 2026-11-08 拍板）**：
> 1. 新增 **UC05 预留与围栏**，插在 UC04 之后，素材来自 BC 读者 Mayank 的三连问，两组探针已实测。
> 2. 原 UC05「多智能体四选一」**拆成四篇**：Swarm / Graph / Workflow / A2A 各一篇，越深入越好。
> 3. 新增 **两篇编排混搭**：同进程混搭、跨进程混搭。
> 4. Guardrails / Evals / Deploy 顺延为 UC12 / UC13 / UC14。
> 5. 系列规模由 8 篇扩为 **14 篇 + A0 概览**；发布节奏由「双周一篇」改为 **每 2–3 天一篇**
>    （依据 2026-11-07 反馈基线：频率换不来阅读，日更会牺牲实测）。

| # | 决策 | 结论 |
|---|---|---|
| A | 系列规模 | **14 篇完整阶梯（D1→D5）+ 1 篇概览** |
| B | 首发篇 | UC01 · The Loop（已发布） |
| C | 仓库组织 | 独立仓库 `strands-in-action`，与 AgentCore 系列双向 cross-link |
| D | 下一篇 | **UC05 · When "Not Found" Doesn't Mean "Never Happened"** |

---

## 1. 系列一句话

> **AgentCore 系列讲的是"云替你扛的那 14 件事"；这个系列讲的是"你自己写代码掌控的那一层"。**

## 2. 难度阶梯

| 难度 | 新增能力 | 参考耗时 | 读者要理解的机制 |
|:--:|---|---|---|
| D1 | 1–2 | ≤ 30 min | agent 跑在哪、一次调用是什么 |
| D2 | 1–2 | ≈ 1 h | 工具的契约、执行的边界 |
| D3 | 2–3 | ≈ 2 h | 状态、隔离、配额的语义 |
| D4 | 3–5 | 3–4 h | 编排、护栏、评测 |
| D5 | 5+ | ≈ 4 h | 部署、上线 |

## 3. 十四个用例（标题 / 状态 / 简介）

| # | 英文标题 | 机制 | D | 状态 | 一句话介绍 |
|---|---|---|:--:|---|---|
| 01 | **How the Strands Agent Loop Actually Works** | agent loop / trace | D1 | ✅ 已发布（四渠道） | 用四行代码起步，追到源码里看清一次调用如何展开：循环是递归不是 `while`，13 种 stop_reason 只有一种会让它继续。 |
| 02 | **The Tools That Got Replaced** | `@tool` / schema / MCP | D2 | ✅ 已发布 | 给 agent 一个计算器和一个读文件工具，说明 docstring 就是 API 契约，以及内置工具层正在经历的迁移。 |
| 03 | **The Limits That Don't Limit** | limits / quota / cancel | D2 | ✅ 已发布 | 一个会失控的 agent 被四类边界拦住：限额只在一次调用内生效，协作式取消才停得下副作用。 |
| 04 | **It Remembers Across Restarts — and Forgets Mid-Conversation** | session / state / 窗口 | D3 | ✅ 已发布（含读者驱动增补） | 重启测试通过，却在同一场对话里把任务约束弄丢：磁盘持久化与 prompt 可见性是两件事，修复要靠注入与检索。 |
| 05 | **When "Not Found" Doesn't Mean "Never Happened"** | 预留 / 崩溃 / 幂等 / fencing | D3 | 🟡 探针已实测，待补真并发实验与正文 | worker 预留配额后崩溃，过期租约把容量还回去，副作用却已发生：只有权威终态或目的地 fencing 才能安全释放。 |
| 06 | **Nobody Decides Who Goes Next** | Swarm | D4 | ⚪ 未开始 | 一群平级 agent 自己决定谁接手，看交接如何触发、上下文如何流动，以及去中心化之后你还能观察到什么。 |
| 07 | **The Graph Is Yours, the Judgment Isn't** | Graph | D4 | ⚪ 未开始 | 把流程画成图，节点、条件路由和状态传播由你定义，判断仍由模型做：确定性来自结构而不是提示词。 |
| 08 | **Less Freedom for the Model, More Certainty for You** | Workflow | D4 | ⚪ 未开始 | 在确定性步骤里嵌入几个 LLM 节点，看输入输出契约如何限制模型的自由度，以及失败之后能从哪一步重放。 |
| 09 | **Your Agent Leaves the Process** | A2A | D4 | ⚪ 未开始 | 两个进程里的 agent 互相调用，协议、序列化、超时与远端失败的可见性全部改变，前面三篇的保证要重新验证。 |
| 10 | **Three Orchestrators, One Process** | Graph + Workflow + Swarm | D4 | ⚪ 未开始 | Graph 定全局、Workflow 定步骤、Swarm 跑局部并行：混搭到底是真需求还是把简单问题复杂化，用对照实验回答。 |
| 11 | **When the Boundary Moves, So Do the Guarantees** | 本地编排 + 远端 A2A | D4 | ⚪ 未开始 | 本地 Graph 调远端 A2A 专家完成一次受限写操作，看进程边界如何改变重试、配额与幂等，并复用 UC05 的 fencing 结论。 |
| 12 | **The Judge Can't Be in the Conversation** | guardrails / HITL | D4 | ⚪ 未开始 | 让 agent 别乱说、关键处停下来问人：做裁决的组件不能是能被对话影响的组件。 |
| 13 | **It Got Worse, and I Can Prove It** | evals / LLM-as-judge | D4 | ⚪ 未开始 | 上线两个月后表现退化，用可度量的评测闭环取代「看着点」，把前面各篇的失败注入变成回归用例。 |
| 14 | **Same Agent, Six Addresses** | 部署目标决策 | D5 | ⚪ 未开始 | 同一个 agent 部署到两个目标并验证行为一致，给出六个落脚点的选择决策树。 |

难度序列 1,2,2,3,3,4,4,4,4,4,4,4,4,5 单调不减 ✓

### 3.1 UC05 详纲（下一篇，优先开工）

**标题候选**：`When "Not Found" Doesn't Mean "Never Happened"`
**读者来源**：Builder Center 读者 Mayank 在 UC03 下的三连问，点名要的失败注入案例。

- 最小用例：一个配额预留器 + 一个外部副作用系统（工单），单槽位、单幂等键
- 四幕递进，全部可复现：
  1. `reserved → crash`：naive 过期归还 → 重复写 + 容量误归还（已有证据 `reservation-crash.txt`）
  2. `outcome_unknown` 与 `unused` 分离，按幂等键对账后才归还（同上）
  3. **延迟提交**：旧 attempt 在对账之后才落库，naive reconciler 依然重复写（`reservation-delayed-commit.txt`）
  4. 目的地 fencing（put-if-absent）与权威 attempt 状态，分别消除"重复写"与"无效重试"
- **需要补做**：真并发版本（线程/进程 + 真实 lease 时钟），把确定性模拟升级为可压力复现的实验；
  与 UC03 的 `max_tool_calls` / `max_tokens` 配额对接，说明 reservation 就是这些限额在多 worker 下的形态
- 明确不写的：不声称证明了任何真实分布式系统的正确性；不把模拟结果说成生产结论
- 关联阅读：UC03（限额）与 UC04（写侧校验）互相引用，UC11 跨进程混搭会复用本篇的 fencing 结论

### 3.2 编排四篇的共同实验台（保证可比性）

四篇共用同一个任务与同一批输入，否则 trace 无法横向比较：

- **共享任务**：给定一个技术主题，产出「调研要点 → 数字核算 → 成稿」三件套；
  拆成 researcher / calculator / writer 三个角色，输入数据固定
- **每篇必测**：真实 trace（交接顺序、调用次数、token 用量）、并行是否真实发生、
  失败注入（让一个角色抛异常/超时，观察编排怎么收场）、人工介入点在哪
- **每篇必答**：这个范式让你放弃了什么（控制权 / 可观测性 / 确定性 / 进程边界）
- **每篇必含**：最小可跑代码、机制源码 `file:line`、真实输出证据、何时不要用

| 篇 | 独占深挖点 |
|---|---|
| 06 Swarm | 交接的触发条件、共享上下文怎么流动、去中心化下的终止条件 |
| 07 Graph | 节点/边/条件路由、状态在图上的传播、循环与收敛 |
| 08 Workflow | 步骤的输入输出契约、LLM 节点与非 LLM 节点的边界、失败重放 |
| 09 A2A | 进程边界、协议与序列化、超时与重试、远端失败的可见性 |

### 3.3 混搭两篇的分工

| 篇 | 场景 | 要回答的问题 |
|---|---|---|
| 10 同进程混搭 | Graph 定全局状态机，Workflow 承载确定性子流程，Swarm 在其中一层做并行调研 | 哪种组合是真需求，哪种是把简单问题复杂化；上下文在三种范式之间怎么传 |
| 11 跨进程混搭 | 本地 Graph + 远端 A2A 专家，任务里包含一次配额受限的写操作 | 进程边界如何改变重试、超时、配额与幂等；复用 UC05 的 fencing 结论 |

## 4. 幕结构（v3）

| 幕 | 篇 | 一句话 |
|---|---|---|
| Principle 原理 | 01 | 循环本身怎么工作 |
| Capability 能力 | 02 工具 / 03 边界 / 04 记忆 / 05 配额语义 | 让它能做更多事，也知道什么时候不做 |
| Orchestration 编排 | 06–09 四种范式 / 10–11 混搭 | 多智能体不是目的，是四种不同的放弃 |
| Production 生产 | 12 护栏 / 13 评测 / 14 部署 | 敢让它上线的最后三道门 |

## 5. 跨篇依赖规则

UC01 已讲透的内容不得重讲，每篇开头一句指明「本文假设你读过哪节」。

| 篇 | 新起点 |
|---|---|
| 02 | 工具的 user 角色回传 + schema 成本 → 从「docstring 即契约」开讲 |
| 03 | 13 种 stop_reason 四分法 → 从「如何主动制造 `limit_*` 终止」开讲 |
| 04 | 状态 = 一个消息列表 → 从「这个列表怎么持久化」开讲 |
| 05 | UC03 的单实例限额 → 从「多个 worker 共享同一份配额时会发生什么」开讲 |
| 06 | UC01 的循环与 UC02 的工具 → 从「让两个 agent 共享同一个循环会怎样」开讲 |
| 07–09 | 前一篇的 trace 结论 → 从「同一个任务，换一种编排」开讲，不重述任务本身 |
| 10 / 11 | 四篇单范式的放弃清单 → 从「把两种范式拼在一起，谁放弃谁」开讲 |
| 12 | `guardrail_intervened` 分组 + hook 否决模型调用 → 从「裁决者不能是对话参与者」开讲 |
| 13 / 14 | 前面各篇的失败注入方法 → 从「怎么证明它没退化 / 怎么换个地方跑」开讲 |

## 6. 文章骨架（不变）

必含元件：可跑的最小用例 + 具体问题开篇；全景图；SDK 源码 `file:line`；why（推断须标注）；
真实运行证据；`What surprised me` / `When not to use this` / `Try it yourself` / takeaways。
字数内容优先，句级纪律不放松；零 Markdown 表格；代码用代码块、运行结果用图。
`src/` 与 `evidence/` 用语义文件名，不加数字前缀。

**v3 新增硬规则**：评论驱动的选题同样必须过 `comment-reply-verification` 的独立验证流程；
正文中每一个数字都要能指回 evidence 文件。

## 7. 发布矩阵与节奏

GitHub Pages（单一真相源）→ Dev.to（canonical 指回）→ Medium（人工）→ Builder Center → 社区。
不做 LinkedIn / DZone / InfoQ。

**每 2–3 天一篇**：D0 发布，D1 回评并把读者发现的缺口补回正文，D2/D3 做下一篇实验。
反馈机制：每日 21:30 图文日报（Dev.to + Builder Center），每周一写作改进复盘。

## 8. 路线图

| 阶段 | 内容 | 完成标志 |
|---|---|---|
| P0–P2 | UC01–UC03 | ✅ 已发布 |
| P3 | UC04 | ✅ 已发布，含读者驱动的两节增补 |
| P4 | **UC05 预留与围栏** | 真并发实验补齐 + 正文 + 四渠道发布 |
| P5 | UC06 Swarm / UC07 Graph | 共享实验台跑通，trace 可横向比较 |
| P6 | UC08 Workflow / UC09 A2A | 同上；A2A 跨进程实测 |
| P7 | UC10 / UC11 混搭 | 复用四篇结论，混搭必要性有实测支撑 |
| P8 | UC12 / UC13 / UC14 | UC14 两个无 Docker 部署目标实测 |
| P9 | A0 概览（14 篇导航） | 覆盖矩阵每项有实证 |

## 9. 风险（v3 更新）

| 风险 | 对策 |
|---|---|
| SDK 发版快 | 每篇标 verified on 日期 + 版本；证据可重跑 |
| UC05 只有确定性模拟，可能被质疑"不是真并发" | 发布前必须补真并发实验；模拟结果只用于解释状态机 |
| 编排四篇共用任务，容易写成重复内容 | 每篇的"独占深挖点"写进大纲评审，重复段落视为返工 |
| 混搭篇最容易变成"为了混而混" | 先写"什么时候不要混搭"，且必须有单一范式做不到的对照实验 |
| Docker 未安装 | UC14 只实测 AgentCore + Lambda 两个目标，其余给决策树 |
