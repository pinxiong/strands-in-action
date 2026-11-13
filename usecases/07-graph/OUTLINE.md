# UC07 大纲 · Orchestrating Agents: The Graph Is Yours, the Judgment Isn't

> 系列第 7 篇（Orchestration 幕第 2 篇，D4）。跨篇依赖：开头一句指明「本文假设你读过
> UC06 的 trace 结论 —— 从同一个任务、同一批输入，换一种编排」，不重述共享任务本身
> （PLAN.md §5 第 07–09 行）。
>
> **下篇开写时必须记住的一条（最近 2–3 篇 feedback 原文口径）**：
>
> 1. `feedback/2026-11-10-uc05-feedback.md`：「读者能复述的是被命名的状态和能跑出真假的
>    判别条件；把结论写成『命名状态 + 真实验 + 显式未验证边界』，然后自己把那些
>    `does not cover` 登记成下一篇的原料，不要等读者来问。」→ 本篇先定三个可复述的
>    命名：`a predicate, not a judge`（条件边是 Python 谓词，模型不参与路由）、
>    `first parent wins`（多入边是 OR，不是 barrier）、`unbounded by default`
>    （不设两个上限就无收敛保证）。
> 2. `feedback/2026-11-11-uc05-feedback.md`：「窗口买到的是曝光，不是互动；UC06 发布后
>    D+2 要盯 Dev.to 评论区是否仍为零，连续两篇为零才构成分发失效证据。」→ 本篇不把
>    互动数据写进技术结论，D+2 单独判读，不混进正文。
> 3. `feedback/2026-11-11-uc01-feedback.md`：「首篇效应是真实的，不为静默改写作规则。」
>    → 本篇不因某一篇的评论量调整结构自检四件套，规则改动只走 `feedback/ledger.md`。
> 4. 另外 UC06 台账「本轮最该记住的一条」：标题的张力表述必须在正文前三段内落地成
>    机制句子。UC07 标题说「judgment isn't yours」，前三段就要点明**哪一段判断被拿走**
>    （节点内部的模型判断保留，路由判断被换成 Python 谓词），不留悬念到中段。
>
> 结构自检四件套（试行，ledger 2026-11-10）：命名状态 / 判别实验 / 显式边界 / 复跑命令。

## 主线（一句话）

Graph 把「谁下一个跑」从模型的工具调用里拿走，交给你写的一张图：节点是你加的、边是你连的、
条件是你写的 Python 谓词。但节点内部仍是完整的 agent 循环，模型依旧决定调用哪个工具、
写什么文本。**结构归你，判断仍归模型**——确定性来自图，不是来自提示词，而图本身也
不保证收敛（默认无上限、多入边是 OR 而非 barrier、状态是拼出来的文本而非共享对象）。

## 五个独家发现（2026-11-13 实测确认，数字见「取证清单」）

1. **条件边是纯 Python 谓词，不是模型判断**：`GraphEdge.should_traverse`
   （graph.py:209-224）只调 `condition(state, invocation_state=...)` 并取 bool；
   `_is_node_ready_with_conditions`（graph.py:1021-1038）遍历入边判定。
   路由决策里没有一次模型调用。所谓「模型判断」只发生在节点内部。
2. **多入边是 OR，不是 barrier**：`_is_node_ready_with_conditions` 里
   `for edge in incoming_edges: ... return True` —— 只要**任一**入边的来源在刚完成的
   batch 里且条件满足，节点就就绪（graph.py:1026-1035）。三个父节点都连到同一个 join，
   第一个父完成就可能放行。命名 `first parent wins`。
3. **状态传播是文本拼接，不是共享对象**：`_build_node_input`（graph.py:1241-1325）
   把 `Original Task:` + 每个已完成依赖的 `str(result)` 拼成 `ContentBlock` 列表，
   格式 `From <dep_id>:\n  - <agent_name>: <result_text>`。下游拿到的是上游**final text**
   的拼串，不是结构化 state；UC06 的 `SharedContext` 是显式对象，两者不是一回事。
4. **默认执行无界**：`GraphState.should_continue`（graph.py:161-179）只在
   `max_node_executions` / `execution_timeout` 设了才收敛；`GraphBuilder._validate_graph`
   （graph.py:491-504）在两个都没设时 `warnings.warn(... execution is unbounded)`。
   `reset_on_revisit` 默认 False（graph.py:324），循环图默认既不重置也不封顶。
   命名 `unbounded by default`。对照 UC06 的 `one counter, two names`。
5. **同批次真并发；但「失败剪枝」在 1.63.0 实测不成立**：`_execute_nodes_parallel`
   （graph.py:872-935）用 `asyncio.create_task` 同时跑整个 batch，E4 实测
   `overlap_pairs=[('right','left')]`。UC06 Swarm 是严格串行，本篇给出硬对照。
   `_find_newly_ready_nodes`（graph.py:999-1018）的 docstring 写着 FAILED 节点被剔除、
   「downstream branch is pruned while sibling branches continue」，**但实测两条注入
   路径都没走到那儿**：
   - E6 `raise`：工具抛异常被 agent 当成一次工具结果，`bad` 节点 `Status.COMPLETED`，
     `bad_downstream` 照跑（order 含四个节点）。
   - E6 `cancel`：`BeforeNodeCallEvent.cancel_node` 在 `_execute_node`（graph.py:1072）
     直接 `raise RuntimeError`，`except` 分支注释明写 "Re-raise to stop graph
     execution (fail-fast behavior)"（graph.py:1227-1229），整图 abort，
     `result_produced=False`，`state_failed_nodes=['bad']` 却没有产生 GraphResult。
   → 正文必须写实测，不许照抄 docstring 的承诺。这是本篇最锋利的一处「文档 ≠ 行为」。

附带源码级（可不跑实验）：节点 executor 若是 Agent 且挂了 session_manager，
构造期直接 `ValueError`（graph.py:301-307，与 Swarm 同）；`BeforeNodeCallEvent.cancel_node`
是人工介入点（graph.py:1066-1068）。

## 可证伪断言（实测逐条判真假，2026-11-13）

| # | 断言 | 实测判定 |
|---|---|---|
| F1 | 条件边求值期间模型调用次数为 0 | **成立**。E2 三次谓词求值的 `model_calls_at_eval` 快照恒为 `{researcher:2, calculator:2, writer:0, fallback:0}`；谓词读的是模型产出的文本，`"3640" in text` 命中 |
| F2 | 多入边 join 是 OR 不是 barrier | **成立且超出预期**。E3 `order=['A','join','B','join']`：join 在 A 完成后立刻跑、与 B 的区间重叠、`join_started_before_B_stopped=True`、输入只有 `From A:`；**B 完成后 join 又被触发第二次**（OR 不检查节点是否跑过） |
| F3 | 下游输入是拼串，含 `Original Task:` 与 `From <dep>:` 字面 | **成立**。E1 writer 首块逐字含 `Original Task:` / `Inputs from previous nodes:` / `From calculator:` / `- Agent:` |
| F4 | 不设两个上限时 build() 发 warning；设上限后循环在 N 次后 FAILED | **成立**。E5 `no_limits_build_warnings=['graph has no ... execution is unbounded']`；capped 模式 `node_executions=6`、`status=FAILED`；timeout_only 模式 6s 超时、只跑了 3 个节点 |
| F5 | 两个同批节点 wall-clock 真相交 | **成立**。E4 `overlap_pairs=[('right','left')]`，2046 tokens / 5.493s |
| F6 | 节点失败会剪枝、兄弟分支继续 | **不成立，已按实测改写**。E6 raise 不产生失败节点；cancel 整图 fail-fast abort。docstring 的承诺在 1.63.0 这两条路径上走不到 |

## 实验台（复用 PLAN §3.2 共享任务，保证与 UC06 及 UC08/09 可比）

- 共享任务：给定一个技术主题，产出「调研要点 → 数字核算 → 成稿」三件套；
  角色 researcher / calculator / writer，输入固定在 `data/brief-input.json`
  （与 UC06 逐字相同，便于跨篇对照 trace）
- 证据要覆盖：真实 trace（执行顺序、每节点模型调用次数、token、耗时）、并行是否真的
  发生（wall-clock overlap）、失败注入、人工介入点
- 模型统一 `amazon.nova-pro-v1:0`（us-east-1），strands-agents 1.63.0，与 UC05/UC06 一致

| # | 脚本 | 场景 | 要证明的 |
|---|---|---|---|
| E1 | `src/graph_trace.py --mode linear` | 三节点链 researcher → calculator → writer | 执行顺序、每节点 token/调用数、writer 拿到的拼串输入逐字 |
| E2 | `src/graph_trace.py --mode condition` | calculator 后两条条件边，一条 True 一条 False | F1：条件求值时模型调用 0；False 分支不进 execution_order |
| E3 | `src/graph_fanin.py --mode or` | 三父 → 一 join，两父人为慢 | F2：first parent wins；join 输入只有一个 `From` |
| E4 | `src/graph_parallel.py --mode overlap` | 两个同批入口节点 | F5：wall-clock overlap 非空（对照 UC06 的空 overlap） |
| E5 | `src/graph_limits.py --mode unbounded` / `--mode capped` | 两节点循环图 | F4：warning、execution_order 长度、status |
| E6 | `src/graph_failure.py --mode raise` / `--mode cancel` / `--mode session` | 节点抛异常 / hook 取消 / session manager | F5 剪枝 + 兄弟分支、人工介入点、构造期 ValueError |

每条进正文的数字必须指回 `evidence/` 里的文件；脚本输出的原始 stdout 直接落盘，
不凭记忆转写。

## 明确不写的（边界声明，定稿时保留）

- 不声称测过任何真实生产多 agent 系统；单机单进程、短任务、固定小样本
- 不比较 Graph 与 Swarm/Workflow/A2A 的优劣（UC08–UC11 的事），只在机制层做一处
  「同任务不同编排」的 trace 对照，且只引用 UC06 已发布的实测数字
- 不覆盖 `session_manager` / `serialize_state` / interrupt resume 的完整语义，
  只在源码引用处提一句 `does not cover`
- 不给出「怎么把 Graph 调可靠」的完整方案；本篇只把结构与判断的界线、以及收敛责任说清
- 不把 Dev.to / BC 的互动数写进技术结论（feedback 第 2 条）

## 标题候选（默认 PLAN 已定值）

| # | 标题 | 优点 | 缺点 |
|---|---|---|---|
| A | **Orchestrating Agents: The Graph Is Yours, the Judgment Isn't** | PLAN 已定，张力直接落在结构/判断的分界上 | 「Judgment Isn't」需前三段立刻落地成机制句 |
| B | Orchestrating Agents: First Parent Wins | 短、点出最锋利的反直觉发现 | 只覆盖一个发现，牺牲结构/判断主线 |
| C | Orchestrating Agents: A Predicate, Not a Judge | 最准确、可验证 | 略抽象，标题泄底 |

默认 A。

## 章节草案（沿用 UC06 骨架，九段顺序以 PLAN §6 元件为准）

1. Intro — 同一个任务，换一种编排：谁决定谁下一个跑？前三段点明路由判断被换成谓词
2. A predicate, not a judge — `should_traverse` 源码 + E2 真实证据
3. First parent wins — `_is_node_ready_with_conditions` 源码 + E3 真实证据
4. State is a string, not a shared object — `_build_node_input` 源码 + E1 输入逐字
5. Unbounded by default — `should_continue` / warning 源码 + E5 真实证据
6. Parallel for real, and a branch that dies — E4 overlap + E6 剪枝
7. What surprised me / When not to use this / Try it yourself / Takeaways

## 取证清单（2026-11-13 全部实测完成）

| 文件 | 内容 | 关键数字 |
|---|---|---|
| `graph-trace-linear.txt/.json` | E1 三节点链 | `COMPLETED`，`['researcher','calculator','writer']`，5109 tokens / 9863ms，每节点 2 次模型调用，`save_draft` 8 词，writer 输入为拼串 |
| `graph-trace-condition.txt/.json` | E2 条件边 | `COMPLETED`，5145 tokens / 31813ms，谓词求值 3 次（fallback 1 + writer 2），三次快照均 `{researcher:2, calculator:2, writer:0, fallback:0}`，`fallback` 未进 order |
| `graph-fanin-or.txt/.json` | E3 OR 而非 barrier | `COMPLETED`，1365 tokens / 9473ms，`order=['A','join','B','join']`，`overlaps=[('join','B')]`，`join_started_before_B_stopped=True`，`from_blocks_in_join_input=['From A:']` |
| `graph-parallel-overlap.txt/.json` | E4 真并行 | `COMPLETED`，2046 tokens / 5493ms，`overlap_pairs=[('right','left')]` |
| `graph-limits-unbounded.txt/.json` | E5 无界 | 不设限 build warning `execution is unbounded`；timeout_only 6s → `FAILED`，3 个节点执行 |
| `graph-limits-capped.txt/.json` | E5 封顶 | 上限 6 → `FAILED`，`node_executions=6` / 644 tokens / 18586ms |
| `graph-failure-raise.txt/.json` | E6 工具异常 | `COMPLETED`，1659 tokens / 4794ms，四节点全跑，`bad_node_status=Status.COMPLETED` |
| `graph-failure-cancel.txt/.json` | E6 hook 取消 | `ABORTED_NO_RESULT`，`RuntimeError: cancelled by a human before the node ran`，`state_failed_nodes=['bad']`，`execution_order=[]` |
| `graph-failure-session.txt/.json` | E6 session | `GraphBuilder.add_node` → `ValueError: Session persistence is not supported for Graph agents yet.` |

SDK 源码出处：`strands/multiagent/graph.py` 161/209/301/324/491/872/999/1021/1042/1072/1139/1176/1227/1241/1425。
版本：strands-agents 1.63.0、`amazon.nova-pro-v1:0`、`us-east-1`（与 UC05/UC06 同）。
