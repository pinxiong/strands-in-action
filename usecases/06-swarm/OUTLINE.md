# UC06 大纲 · Orchestrating Agents: Nobody Decides Who Goes Next

> 系列第 6 篇（Orchestration 幕第 1 篇，D4）。跨篇依赖：开头一句指明「本文假设你读过
> UC01 的循环与 UC02 的工具 —— 一个节点就是一次完整的 agent 循环，交接就是一个工具调用」。
>
> **下篇开写时必须记住的一条（来自 `feedback/2026-11-10-uc05-feedback.md`）**：
> 读者能复述的是被命名的状态和能跑出真假的判别条件；把结论写成「命名状态 + 真实验 +
> 显式未验证边界」，然后自己把那些 `does not cover` 登记成下一篇的原料，不要等读者来问。
> 本篇据此先定下三个命名：`completion by silence`（无交接即完成）、`rebuilt prompt`
> （上下文重建而非转发）、`one counter, two names`（`max_handoffs` 与 `max_iterations`
> 是同一个计数器）。连带规则（UC05 已立）：边界类文章必须写到「边界之外靠什么」。

## 主线（一句话）

Swarm 里没有一个调度者在决定谁下一个跑：运行时是一个 `while True`，每一轮问当前节点
「你要不要交接」，节点唯一能表达「交接」的方式是调用注入给它的 `handoff_to_agent` 工具；
不调用就等于宣布任务完成。所谓去中心化，是把路由决策放进模型的工具列表里，
代价是终止条件变成了沉默、上下文只能重建、并行根本不存在。

## 五个独家发现（待实测填数字，2026-11-11）

1. **完成由沉默判定**：`_execute_swarm` 在节点结束后检查 `state.handoff_node`，为空即
   `completion_status = COMPLETED`（swarm.py:954-957）。因此 `COMPLETED` 的语义是
   「没有节点要求接力」，不是「任务做完了」。
2. **交接是一次状态写入，在轮次结束后才生效**：`handoff_to_agent` 只写
   `state.handoff_node` / `handoff_message`（swarm.py:689-690），真正的跳转发生在节点
   收尾之后（swarm.py:932）。节点可以在交接后继续干活，最后一次交接覆盖前一次。
3. **节点失败会回滚它请求的交接**：`_rollback_uncommitted_turn`（swarm.py:703-713）
   把 `handoff_node` 还原成轮次开始前的值 —— 一个节点临死前请求的接力不算数。
4. **上下文是重建的，不是转发的**：每个节点开跑前 `reset_executor_state`
   （swarm.py:999）把消息历史重置回构造时的状态，再喂一段 `_build_node_input`
   （swarm.py:715-787）拼出来的文本：交接消息 + 用户请求 + 历史节点 + `shared_context`
   + 同伴清单。消息历史不跨节点，`SharedContext` 是唯一通道，且写在**发送者**名下
   （swarm.py:695）。
5. **`max_handoffs` 与 `max_iterations` 是同一个计数器**：两者都与
   `len(node_history)` 比较（swarm.py:211 / 215），谁小谁生效；且触顶被报成
   `FAILED` 而不是 `COMPLETED`（swarm.py:836）。

附带两条（源码级，可不跑实验）：Swarm 各节点的 agent 不允许挂 session manager
（swarm.py:611-612）；`deserialize_state` 文档明写恢复是 at-least-once，节点必须幂等
（swarm.py:1163-1166）—— 这条接 UC05 的幂等结论。

## 实验台（复用 PLAN §3.2 共享任务，保证与 UC07–UC09 可比）

- 共享任务：给定一个技术主题，产出「调研要点 → 数字核算 → 成稿」三件套；
  角色 researcher / calculator / writer，输入数据固定在 `data/brief-input.json`
- 证据要覆盖：真实 trace（交接顺序、每节点调用次数、token、耗时）、并行是否真的发生、
  失败注入（节点抛异常 / 节点被 hook 取消）、人工介入点在哪

| # | 脚本 | 场景 | 要证明的 |
|---|---|---|---|
| E1 | `src/swarm_trace.py --mode happy` | 三节点正常接力到 writer | 交接顺序真实 trace、每节点 token、串行时间线、节点拿到的输入文本 |
| E2 | `src/swarm_trace.py --mode silent` | 入口节点直接回答不交接 | `COMPLETED` + `execution_count=1`，writer 从未跑、`save_draft` 0 次 |
| E3 | `src/swarm_limits.py --cap iterations` / `--cap handoffs` | 两节点互相踢皮球 | 两个上限是同一个计数器；触顶状态是 `FAILED` |
| E4 | `src/swarm_failure.py --mode raise` | 节点先请求交接再抛异常 | 交接被回滚，writer 不在 history 里 |
| E5 | `src/swarm_failure.py --mode cancel` | `BeforeNodeCallEvent` 取消第二个节点 | 人工介入点就在这个 hook；取消后整盘 `FAILED` |
| E6 | `src/swarm_failure.py --mode session` | 给节点 agent 挂 session manager | 构造期直接 `ValueError`（不用调模型） |

模型统一 `amazon.nova-pro-v1:0`（us-east-1），与 UC05 一致，成本可控。
每条进正文的数字必须指回 `evidence/` 里的文件。

## 明确不写的（边界声明，定稿时保留）

- 不声称测过任何真实生产多 agent 系统；单机单进程三节点、短任务
- 不比较 Swarm 与 Graph/Workflow/A2A 的优劣（那是 UC07–UC09 的事），只在末尾一句带过系列走向
- 不给「怎么让 swarm 变可靠」的完整方案；本篇只把机制与代价说清
- 不覆盖 `repetitive_handoff_detection_window`（默认关闭）的效果，只在源码引用处提一句

## 标题候选（默认 PLAN 已定值）

| # | 标题 | 优点 | 缺点 |
|---|---|---|---|
| A | **Orchestrating Agents: Nobody Decides Who Goes Next** | PLAN 已定，直接说出范式特征，与子系列前缀一致 | 「Nobody」稍绝对，需正文立刻解释 |
| B | Orchestrating Agents: Silence Means Done | 短、直接点出本篇最锋利的发现 | 牺牲「去中心化」这层 |
| C | Orchestrating Agents: The Handoff Is Just a Tool Call | 最准确、可验证 | 长了，且标题泄底 |

默认 A。

## 章节草案

1. Intro — 三个 agent，一个任务，没有调度者：谁决定谁下一个跑？
2. The whole scheduler is one tool — `handoff_to_agent` 注入 + `while True` 结构 + 源码
3. `completion by silence` — E1/E2 对照：任务没做完也会 COMPLETED
4. `rebuilt prompt` — 节点消息历史被重置，上下文只有一段拼出来的文本 + shared_context（写在发送者名下）
5. One counter, two names — E3；触顶是 FAILED
6. When a node dies mid-handoff — E4/E5；回滚 + hook 取消 = 人工介入点
7. What surprised me / When not to use this / Try it yourself / Takeaways

## 取证清单（已完成，2026-11-11）

| 文件 | 内容 | 关键数字 |
|---|---|---|
| evidence/swarm-trace.txt | E1 两次正常接力 + E2 沉默 | E1a 8857 tokens / 15.299s / 3+3+2 次模型调用 / 8 词稿；E1b 8605 tokens / 6 词稿；E2 completed + execution_count 1 / 718 tokens / ledger 空 |
| evidence/swarm-limits.txt | E3 两档上限 | 都是 3 轮后 failed；5704 vs 5584 tokens；reason 分别是 Max iterations / Max handoffs reached: 3 |
| evidence/swarm-failure.txt | toolerror / timeout / cancel / session | toolerror completed + 22371 tokens + 45.967s + 11 次 save_draft；timeout failed + execution_count 0 + 0 tokens + 4.012s；cancel failed + 3194 tokens；session ValueError |
| evidence/*.json | 各次运行原始字段 | 同上 |

SDK 源码出处：`strands/multiagent/swarm.py` 211/215/611/689/695/703/715/836/932/954/999/1163。
版本：strands-agents 1.63.0（与 UC05 同版本，便于跨篇对照）。
