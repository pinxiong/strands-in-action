# 流水线状态（三个触发点共享，谁先醒谁干活，后来者只检查）

> 流程见 [`PIPELINE.md`](PIPELINE.md)；发布时间依据 [`PUBLISHING-POLICY.md`](PUBLISHING-POLICY.md)；反馈闭环见 `writing-lab/feedback/README.md`。

## 机器可读字段（自动任务先读这几行）

```yaml
last_run_date: 2026-11-08      # 最近一次真正推进过工作的日期
today_started: 2026-11-08      # 今天是否已开工（与 last_run_date 同步；跨天自动失效）
stage: not_started             # not_started | outline | experiments | draft | review | ready_to_publish | published
current_piece: UC05
gates: {}                      # 三类评审结果，例：{expert: pass, reader: fail, independent: pass}
ready_since: null              # 评审全 PASS 的时间；非空且落在发布窗口就发
```

## 当前

| 项 | 值 |
|---|---|
| 当前篇目 | **UC05 · When "Not Found" Doesn't Mean "Never Happened"** |
| 阶段 | `not_started` |
| 最近发布日期 | 2026-11-07（UC04 `it-remembers-across-restarts-and-forgets-mid-conversation`） |
| 下次可开新篇 | 2026-11-09（10:30 档） |
| 下次可发布窗口 | 2026-11-10 21:30–22:30（GMT+8，周二）；若 11-09 当天全 PASS 则 11-09 21:30 可发（周一，允许） |
| 阻塞项 | UC05 必须补**真并发实验**（线程/进程 + 真实 lease 时钟）；`outreach/uc03-comments/` 两组探针只用于解释状态机 |

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
