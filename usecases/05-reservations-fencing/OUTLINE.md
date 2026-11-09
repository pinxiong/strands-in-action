# UC05 大纲 · When "Not Found" Doesn't Mean "Never Happened"

> 系列第 5 篇（Capability 幕第 4 篇，D3）。跨篇依赖：开头一句指明「本文假设你读过 UC03 的
> 限额实验 —— `limits` 只在一次调用内计数，新的顶层调用拿到全新预算」。
>
> **下篇开写时必须记住的一条（来自 2026-11-08 UC03 反馈记录）**：
> 判断反馈是「澄清」还是「缺口」：澄清改正文，缺口改计划。本篇本身就是这个判断的产物
> （Mayank 三连问是缺口，不是澄清）。连带规则：写「边界类」文章，结论必须写到
> 「边界之外靠什么」—— 本篇的「之外」= 幂等键对账 + 目的地 fencing。
>
> 读者来源：Builder Center 读者 Mayank Raj 在 UC03 下的三连问，点名要的失败注入案例。

## 主线（一句话）

租约过期只能证明「worker 停止汇报」，不能证明「操作没有发生」；把过期当 `unused`
会在崩溃边界和延迟提交两个场景里同时造成重复写与容量误归还，安全释放只有两条路：
按幂等键对账到权威终态，或让目的地用 put-if-absent 围栏挡住迟到的提交。

## 五个独家发现（全部实测，2026-11-09，证据见 `evidence/`）

1. **一个实例串行、两个实例两份预算**：同一 Agent 实例的并发调用直接
   `ConcurrencyException`（agent.py:268，THROW 默认）；带相同 `idempotency_token`
   的重复请求不重跑模型，等在途结果拿缓存（`_concurrency.py:183`，实测
   primary 与 duplicate usage 完全相同 948 tokens）；两个实例并发时各自
   `stop=limit_turns`、各 453 tokens（C4）——进程内 SDK 做了串行与去重，
   跨实例/跨进程的共享配额依然要自己建。
2. **expiry ≠ outcome**：worker 停止汇报后，`unused`（没发生过）与
   `outcome_unknown`（不知道有没有发生）是两个状态；naive 归还把二者混为一谈
   —— 5/5 次重复写 + 5/5 次容量误归还（C1）。
3. **崩溃边界两边都不安全**：effect 之前崩溃，容量也要等满租约 1.0s 才回来
   （C3：继承者实测等 1.002s / 1.001s / 1.0s，三轮复现）；effect 之后崩溃，
   naive 直接重复写（C1 after-effect 组）。
4. **absence 是时间点快照不是承诺**：对账时 `not found`、提交时却 `found`
   —— 真实时钟下旧 attempt 在 1.005s 被判 `unused` 后，2.405s 才落库，
   naive reconciler 5/5 次重复写（C2）。
5. **fencing 挡重复写但救不回浪费**：put-if-absent 把 duplicate 归零（5/5），
   但旧 attempt 烧满 2.404s 才被拒（`ok=False`，被拒的是它）；只有目的地暴露
   attempt 状态，对账才能不提前释放（released@2.405s = 终态出现之后）、
   重试才不会白跑（C2 authoritative 组：retry_started=0/5）。

## 四幕递进（全部真时钟真线程，可复现）

1. **reserved → crash**：naive 过期归还 → 重复写 + 容量误归还；
   reconcile 按 `confirmed_existing` / `unused` 分流。崩溃点在 effect 前后各自成证。
2. **outcome_unknown 与 unused 分离**：对账语义本身就是状态机扩展，不是策略开关。
3. **延迟提交**（本篇核心增量，UC03 评论区探针没有的）：旧 attempt 在对账之后才落库，
   naive reconciler 依然重复写 —— 真实 lease 时钟 + 真线程重叠，压力复现。
4. **目的地 fencing（put-if-absent）与权威 attempt 状态**：分别消除「重复写」与「无效重试」；
   两者解决的是不同的一半，对照表说清。

## 实验设计（真并发升级，全部本篇 `src/` + `evidence/`）

| # | 脚本 | 场景 | 对照 |
|---|---|---|---|
| C1 | `lease_crash_boundary.py` | worker 预留后崩溃（effect 前/后），janitor 线程按真实时钟判过期 | naive vs reconcile × 崩溃点 |
| C2 | `delayed_commit_race.py` | 旧 attempt 跨过租约存活，对账后落库；`--stress N` 压力复现 | naive vs fenced vs authoritative |
| C3 | `slot_contention.py` | 8 线程抢 2 个带租约的 slot，其中 1 个 worker 崩溃占位 | 争用 + 过期回收的真实时长 |
| C4 | `concurrent_limits.py` | 两个线程并发 invocation，各自带 `limits`，nova-pro | 证明预算按调用隔离 |

确定性探针（`outreach/uc03-comments/` 两组）在文中只用于解释状态机，明确标注
"确定性模拟"；本篇所有进正文的数字来自 C1–C4 真实运行。

## 明确不写的（边界声明）

- 不声称证明了任何真实分布式系统的正确性；单机线程 + 真实时钟 ≠ 分布式
- 不把模拟/压测结果说成生产结论
- 不引入真实数据库 / ZooKeeper / etcd；目的地用线程锁模拟互斥，声明这是模拟
- 不重讲 UC03 的限额机制（一句带过 + 链接），不重讲 UC04 的写侧校验（一句带过 + 链接）

## 关联阅读

UC03（限额，`limits-reset` 证据）、UC04（写侧校验 / 幂等键的持久化一側）、
UC11（跨进程混搭将复用本篇 fencing 结论）。

## 标题候选（发布前定稿）

| # | 标题 | 优点 | 缺点 |
|---|---|---|---|
| A | **When "Not Found" Doesn't Mean "Never Happened"** | PLAN 已定，直接点出核心认知误区 | 偏长 |
| B | **The Lease That Lies** | 短、张力强 | 太玄，牺牲精确性 |
| C | **Not Found Is Not Never** | 短 + 口语化 | 略随意 |

默认 A（PLAN.md 拍板值）。

## 取证清单（已完成，2026-11-09）

| 文件 | 内容 | 关键数字 |
|---|---|---|
| evidence/lease-crash-boundary.txt | C1 真时钟崩溃边界，4 组合 × 5 次 | naive/after-effect：duplicates 5/5、误归还 5/5；reconcile 全 0 |
| evidence/delayed-commit-race.txt | C2 三模式 × 5 次压力复现 | naive duplicates 5/5；fenced 0 但旧 attempt 5/5 被拒；authoritative 0 提前释放 |
| evidence/slot-contention.txt | C3 争用与过期回收 × 3 轮 | 崩溃 slot 仅经 expiry 回收，继承者等待 1.002/1.001/1.0s ≈ 租约 1.0s |
| evidence/concurrent-limits.txt | C4 三段式 LLM 探针（nova-pro） | 实例串行 ConcurrencyException；同 token 去重缓存（948 tokens 一致）；双实例各 453 tokens |

SDK 源码出处（评审用）：`strands/agent/agent.py:268`（THROW 默认）、
`strands/agent/agent.py:928`（idempotency_token 参数）、
`strands/agent/_concurrency.py:107`（begin：幂等检查 + 锁获取合并）、
`strands/agent/_concurrency.py:183`（_check_idempotency）、
`strands/types/agent.py:205`（ConcurrentInvocationMode 枚举）。
版本：strands-agents 1.63.0。

## 章节草案（对齐四幕 + 骨架硬规则）

1. Intro — Mayank 三连问原话引入：单次调用的限额管不住并发 attempt
2. What the SDK already does — C4 三段：实例串行 / 进程内幂等令牌去重 /
   跨实例各拿预算；结论：跨 worker 共享配额是自己的一层
3. What a lease can and cannot tell you — C1：expiry 只证明停止汇报
4. `unused` vs `outcome_unknown` — 状态机扩展（确定性探针图示）
5. The retry that arrives too early — C2 延迟提交竞态（本篇核心）
6. Fences and witnesses — put-if-absent vs authoritative attempt state 对照
7. What surprised me / When not to use this / Try it yourself / Takeaways
