# 流水线状态（三个触发点共享，谁先醒谁干活，后来者只检查）

> 流程见 [`PIPELINE.md`](PIPELINE.md)；发布时间依据 [`PUBLISHING-POLICY.md`](PUBLISHING-POLICY.md)；反馈闭环见 `writing-lab/feedback/README.md`。

## 机器可读字段（自动任务先读这几行）

```yaml
last_run_date: 2026-11-09      # 最近一次真正推进过工作的日期
today_started: 2026-11-09      # 今天是否已开工（与 last_run_date 同步；跨天自动失效）
stage: experiments             # not_started | outline | experiments | draft | review | ready_to_publish | published
current_piece: UC05
gates: {}                      # 三类评审结果，例：{expert: pass, reader: fail, independent: pass}
ready_since: null              # 评审全 PASS 的时间；非空且落在发布窗口就发
```

## 当前

| 项 | 值 |
|---|---|
| 当前篇目 | **UC05 · When "Not Found" Doesn't Mean "Never Happened"** |
| 阶段 | `experiments`（大纲 + 真并发实验已完成，2026-11-09 10:30 档；下一步：英文正文） |
| 最近发布日期 | 2026-11-07（UC04 `it-remembers-across-restarts-and-forgets-mid-conversation`） |
| 下次可开新篇 | 2026-11-11（UC05 发布后满 2 天） |
| 下次可发布窗口 | 2026-11-09 21:30–22:30（GMT+8，周一，允许）；前提：正文 + 三类评审全 PASS |
| 阻塞项 | 无。真并发实验已补齐（C1–C4，证据在 `usecases/05-reservations-fencing/evidence/`）；`outreach/uc03-comments/` 两组探针只用于解释状态机 |

## UC05 实验台账（2026-11-09 10:30 档产出）

- 大纲：`usecases/05-reservations-fencing/OUTLINE.md`（五个独家发现已回填实测数字）
- C1 崩溃边界（真时钟 4 组合 × 5 次）：naive/after-effect 重复写 5/5 + 误归还 5/5
- C2 延迟提交竞态（3 模式 × 5 次压力）：naive 5/5 重复；fenced 0 重复但旧 attempt 5/5 被拒；authoritative 0 提前释放
- C3 slot 争用（× 3 轮）：崩溃 slot 仅经 expiry 回收，继承者等待 ≈ 租约 1.0s
- C4 三段式 LLM 探针（nova-pro，strands 1.63.0）：实例串行 ConcurrencyException / 同 idempotency_token 进程内去重 / 双实例各拿预算
- SDK 源码出处已取：agent.py:268/928、_concurrency.py:107/183、types/agent.py:205

## 历史

| 日期 | 篇目 | 结果 |
|---|---|---|
| 2026-11-07 | UC04 Sessions, State & Memory | 已发布（主站 / Dev.to / BC） |
| 2026-11-06 | UC03 The Limits That Don't Limit | 已发布 |
| 2026-11-05 | UC02 The Tools That Got Replaced | 已发布 |
| 2026-11-04 | UC01 How the Strands Agent Loop Actually Works | 已发布 |

## 顺延记录

| 日期 | 原因 | 顺延到 | 从哪继续 |
|---|---|---|---|
| — | — | — | — |
