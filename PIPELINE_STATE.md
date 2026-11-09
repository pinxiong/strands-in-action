# 流水线状态（三个触发点共享，谁先醒谁干活，后来者只检查）

> 流程见 [`PIPELINE.md`](PIPELINE.md)；发布时间依据 [`PUBLISHING-POLICY.md`](PUBLISHING-POLICY.md)；反馈闭环见 `writing-lab/feedback/README.md`。

## 机器可读字段（自动任务先读这几行）

```yaml
last_run_date: 2026-11-09      # 最近一次真正推进过工作的日期
today_started: 2026-11-09      # 今天是否已开工（与 last_run_date 同步；跨天自动失效）
stage: published               # not_started | outline | experiments | draft | review | ready_to_publish | published
current_piece: UC05
gates: {expert: pass, reader: pass, independent: pass}
ready_since: 2026-11-09T11:20+08:00
published_at: 2026-11-09T13:32:00Z   # 主站 push 时刻（UTC）
```

## 当前

| 项 | 值 |
|---|---|
| 当前篇目 | **UC05 · When "Not Found" Doesn't Mean "Never Happened"** — 已发布（2026-11-09） |
| 阶段 | `published`（21:30 档完成发布：主站 / Dev.to / BC） |
| 最近发布日期 | 2026-11-09（UC05 `reservations-fencing`） |
| 下次可开新篇 | 2026-11-11（UC05 满 2 天，写 UC06 Swarm） |
| 下次可发布窗口 | UC06 完成后：2026-11-11 起的工作日 21:30–22:30（GMT+8） |
| 阻塞项 | 无。待办只有反馈回灌：UC05 D+2 = 2026-11-11，UC04 D+7 = 2026-11-14 |

## UC05 D+0 台账（2026-11-09）

| 项 | 值 |
|---|---|
| 标题 | When "Not Found" Doesn't Mean "Never Happened" |
| 主站 | https://xiongpin.dev/posts/reservations-fencing/ — push 21:32:00（GMT+8）= 13:32:00 UTC，21:36 起 200 |
| Dev.to | https://dev.to/aws-builders/when-not-found-doesnt-mean-never-happened-2eie — id 5004687，21:33:25（GMT+8）= 13:33:25 UTC，org aws-builders（2794），canonical 指回主站 |
| Builder Center | https://builder.aws.com/content/3Ls8Su63RbuSKR3yys1j9t6US1p/when-not-found-doesnt-mean-never-happened — ≈22:15（GMT+8）= 14:15 UTC，200，hero 封面与 "Originally published" 均在线上 |
| Medium | 未发（人工物料，今晚不动） |
| 规模 | 正文 2251 词（不含代码块）/ 16 个代码块 / 4 组实验（C1 崩溃边界、C2 延迟提交竞态、C3 slot 争用、C4 LLM 三探针） |
| 指标 | final_check 0 项；stdev 8.2（舒适区下限 8，余量 0.1） |

**发布当天的两个已知偏差（非阻塞，留给下次改进）**

1. BC 封面 `cover-medium.png` 是 1400×735（1.90:1），SKILL 要求 16:9（1400×788）。线上 hero 已显示，但可能有裁切；下次出图时把 `cover.svg` 的 viewBox 直接做到 16:9。
2. BC `cover` 步骤报了两次 "改动没进草稿" 的 FAIL，实为 SKILL troubleshooting §11 的已知误判：第一次上传已落库（`prod-assets.../cove.webp`），第二次重传资产 URL 不变被判失败。核验方式是看"当前已保存封面"那行，不是等 `Saved cover asset` 二次变化。

## UC05 评审台账（2026-11-09）

| 评审 | 首轮 | 修订后复审 |
|---|---|---|
| 技术专家 | FAIL 4 项（compose 越界断言、453 是 usage 非 budget 且出处错、first call won、janitor thread） | PASS 7/7 |
| 目标读者 | 有条件 PASS，5 处必改（idempotency_token 定义、争用实验进正文、fence 语义、in_flight 前提、状态图 naive 路径） | PASS 5/5 |
| 独立复核 | FAIL 1 项（句长标准差 7.0 < 8）；硬规则全过 | PASS（stdev 8.2、final_check 0 项） |

## UC05 实验台账（2026-11-09 10:30 档产出）

- 大纲：`usecases/05-reservations-fencing/OUTLINE.md`（五个发现已回填实测数字）
- C1 崩溃边界（真时钟 4 组合 × 5 次）：naive/after-effect 重复写 5/5 + 误归还 5/5
- C2 延迟提交竞态（3 模式 × 5 次压力）：naive 5/5 重复；fenced 0 重复但旧 attempt 5/5 被拒；authoritative 0 提前释放
- C3 slot 争用（× 3 轮）：崩溃 slot 仅经 expiry 回收，继承者等待 ≈ 租约 1.0s
- C4 三段式 LLM 探针（nova-pro，strands 1.63.0）：实例串行 ConcurrencyException / 同 idempotency_token 进程内去重 / 双实例各拿预算
- SDK 源码出处已取：agent.py:268/928/955、_concurrency.py:25/86/107/183、types/agent.py:205

## 发布物料（已归档，均为线上状态）

- 主站：`pinxiong.github.io/content/posts/reservations-fencing.md`（`draft: false`，commit a43e079）
- 图片：`pinxiong.github.io/static/images/reservations-fencing/`（cover / cover-devto / cover-medium / race-timeline）
- Dev.to：`usecases/05-reservations-fencing/publish/devto.md`（`build_devto.py --check` = in sync）
- BC / Medium：`usecases/05-reservations-fencing/publish/reservations-fencing.md`（本次改动：标题去转义、正文图改站内根路径）
- **评审预览**：`usecases/05-reservations-fencing/review/article-preview.html`
- 正文：2251 词、final_check 0 项（发布后 30 分钟内未改正文，符合 PUBLISHING-POLICY §5.4）

## 历史

| 日期 | 篇目 | 结果 |
|---|---|---|
| 2026-11-09 | UC05 When "Not Found" Doesn't Mean "Never Happened" | 已发布（主站 / Dev.to / BC），D+2 = 11-11 |
| 2026-11-07 | UC04 Sessions, State & Memory | 已发布，D+2 记录已补（2026-11-09），D+7 = 11-14 |
| 2026-11-06 | UC03 The Limits That Don't Limit | 已发布 |
| 2026-11-05 | UC02 The Tools That Got Replaced | 已发布 |
| 2026-11-04 | UC01 How the Strands Agent Loop Actually Works | 已发布 |

## 顺延记录

| 日期 | 原因 | 顺延到 | 从哪继续 |
|---|---|---|---|
| — | — | — | — |
