# 流水线状态（三个触发点共享，谁先醒谁干活，后来者只检查）

> 流程见 [`PIPELINE.md`](PIPELINE.md)；发布时间依据 [`PUBLISHING-POLICY.md`](PUBLISHING-POLICY.md)；反馈闭环见 `writing-lab/feedback/README.md`。

## 机器可读字段（自动任务先读这几行）

```yaml
last_run_date: 2026-11-09      # 最近一次真正推进过工作的日期
today_started: 2026-11-09      # 今天是否已开工（与 last_run_date 同步；跨天自动失效）
stage: draft                   # 回到修订：Kent 五项追问（18:30 到）晚于正文定稿（17:00），周复盘判定必须先补
current_piece: UC05
gates: {}                      # 新增小节后三类评审需重跑（此前 2026-11-09 11:20 全 PASS 的结论只覆盖旧版正文）
ready_since: null             # 清空：等新增小节过完三类评审再置回
```

## 当前

| 项 | 值 |
|---|---|
| 当前篇目 | **UC05 · When "Not Found" Doesn't Mean "Never Happened"** |
| 阶段 | `draft`（回修：补「何时转人工」小节，见顺延记录） |
| 最近发布日期 | 2026-11-07（UC04 `it-remembers-across-restarts-and-forgets-mid-conversation`） |
| 下次可开新篇 | UC05 发布后满 2 天（预计 2026-11-11，写 UC06 Swarm） |
| 下次可发布窗口 | **2026-11-10 21:30–22:30（GMT+8，周二，策略首选日）**；今晚 21:30 档只做检查，不发 |
| 阻塞项 | 正文需补 Kent 五项（scope owner / decision deadline / forced timeout + external read-back / recovery owner / 停止自动 reconciliation 转人工的判据），补完重跑三类评审与渠道重建 |

## UC05 评审台账（2026-11-09）

| 评审 | 首轮 | 修订后复审 |
|---|---|---|
| 技术专家 | FAIL 4 项（compose 越界断言、453 是 usage 非 budget 且出处错、first call won、janitor thread） | PASS 7/7 |
| 目标读者 | 有条件 PASS，5 处必改（idempotency_token 定义、争用实验进正文、fence 语义、in_flight 前提、状态图 naive 路径） | PASS 5/5 |
| 独立复核 | FAIL 1 项（句长标准差 7.0 < 8）；硬规则全过 | PASS（stdev 8.2、final_check 0 项） |

复审后的非阻塞微调（引用锚点 :107→:86、多 worker 超配一句、slot 数切换说明、状态图 in_flight 自环）已落地并重跑指标确认无回归。

## UC05 实验台账（2026-11-09 10:30 档产出）

- 大纲：`usecases/05-reservations-fencing/OUTLINE.md`（五个发现已回填实测数字）
- C1 崩溃边界（真时钟 4 组合 × 5 次）：naive/after-effect 重复写 5/5 + 误归还 5/5
- C2 延迟提交竞态（3 模式 × 5 次压力）：naive 5/5 重复；fenced 0 重复但旧 attempt 5/5 被拒；authoritative 0 提前释放
- C3 slot 争用（× 3 轮）：崩溃 slot 仅经 expiry 回收，继承者等待 ≈ 租约 1.0s
- C4 三段式 LLM 探针（nova-pro，strands 1.63.0）：实例串行 ConcurrencyException / 同 idempotency_token 进程内去重 / 双实例各拿预算
- SDK 源码出处已取：agent.py:268/928/955、_concurrency.py:25/86/107/183、types/agent.py:205

## 发布物料（已就绪，21:30 档直接用）

- 主站草稿：`pinxiong.github.io/content/posts/reservations-fencing.md`（`draft: true`，Hugo `-D` 构建通过，og:image 正常，无 front matter 泄漏）
- 图片：`pinxiong.github.io/static/images/reservations-fencing/`（cover / cover-devto / cover-medium / race-timeline，PNG + SVG 源）
- Dev.to：`usecases/05-reservations-fencing/publish/devto.md`（`build_devto.py --check` = layout only + in sync）
- BC / Medium：`usecases/05-reservations-fencing/publish/reservations-fencing.md`
- 仓库说明：`usecases/05-reservations-fencing/publish/README.md`
- **评审预览**：`usecases/05-reservations-fencing/review/article-preview.html`（已递 Pin；正文再改要重新生成，命令见 PIPELINE.md 第 5 节）
- **渠道正文同步**：`build_devto.py` 只做折行展开，不搬内容；改 article.md 后必须按「article 正文（去 H1）→ 各渠道 front matter + 图片域名替换」重建 devto.md / reservations-fencing.md / Hugo 草稿，再跑 `python tools/build_devto.py --check`（应 4 项全 `layout only` + `in sync`）与 `hugo -D` 校验。
- 正文：2421 词、16 个代码块（9 python / 6 text / 1 bash）、final_check 0 项；avg 16.2w / stdev 9.8、被动 3.1、连接词 1.07、名词化 3.06、Flesch 61.9
- **指标口径坑（重要）**：`en_metrics.py` 把 fenced code 替换成空行，冒号句会和代码块之后的散文粘成一句，于是报 `>40w = 4`。按"代码块自成句读"重算：165 句、`>40w = 0`（最长 35 词）。别为此改句子。
- **源码引用已全部内联**（2026-11-09 用户要求）：SDK 五处（agent.py:268 / 924-929 / 956-957、_concurrency.py:183 / 95、types/agent.py:205）与实验脚本四处（lease_crash_boundary.py:56 / 99、delayed_commit_race.py:46 / 99）都是逐字代码块，首行标 `path:line -- version`；链接只作二级指针。理由：SDK 升级后行号会指向别的代码。

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
| 2026-11-09 | Kent Bodrov 18:30 在 UC03 追问 unresolved 队列治理五项，晚于正文定稿（17:00）；周复盘（20:20）判定 UC05 不补这节不得进窗口 | 2026-11-10 21:30–22:30（周二，发布策略首选日） | 明天 10:30 档：补「When a human is needed」小节 → 重跑三类评审 → 重建三渠道物料 → 21:30 窗口发布 |
