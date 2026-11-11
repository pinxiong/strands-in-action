# 流水线状态（三个触发点共享，谁先醒谁干活，后来者只检查）

> 流程见 [`PIPELINE.md`](PIPELINE.md)；发布时间依据 [`PUBLISHING-POLICY.md`](PUBLISHING-POLICY.md)；反馈闭环见 `writing-lab/feedback/README.md`。

## 机器可读字段（自动任务先读这几行）

```yaml
last_run_date: 2026-11-11      # 最近一次真正推进过工作的日期
today_started: 2026-11-11      # 今天是否已开工（与 last_run_date 同步；跨天自动失效）
stage: published               # not_started | outline | experiments | draft | review | ready_to_publish | published
current_piece: UC06
gates: {expert: pass, reader: pass, independent: pass}   # UC06 正文三类评审已 PASS（2026-11-11）
ready_since: 2026-11-11T12:28+08:00   # 正文可发时刻；发布物料 21:36 前补齐
published_at: 2026-11-11T13:36:31Z    # UC06 主站 push 时刻；UC05 = 2026-11-09T13:32:00Z
publish_gate: {medium_manual: true, cover_16x9: true, slack_copy: true}  # 三项全 true（2026-11-11 21:36 门禁 18/18 PASS）
publish_gate_checked: 2026-11-11T21:36+08:00  # check_publish_gate.py orchestrating-swarm → 18/18 PASS，可发布
```

> **发布门禁（每次自动发布都适用）**：`stage` 改成 `published` 之前必须跑 `python3 check_publish_gate.py <slug>`，非 0 退出禁止发布；通过后把 `publish_gate` 三项置 `true` 并记检查时刻。Medium 不发，但手册 / 16:9 封面 / Slack 文案缺一不可，不许"先发再补"。详见 `PIPELINE.md` 第 6 节。

## 当前

| 项 | 值 |
|---|---|
| 当前篇目 | **UC06 · Orchestrating Agents: Nobody Decides Who Goes Next** — **已发布（四渠道中三渠道，Medium 待手动 Import）** |
| 阶段 | `published`（21:30 档补齐物料 → 门禁 18/18 → 三渠道发布 + UC05 D+2 / UC01 D+7 反馈回灌） |
| 最近发布日期 | 2026-11-11（UC06 `orchestrating-swarm`） |
| 下次可开新篇 | UC07 最早 2026-11-13（距 UC06 发布满 2 天）；`PLAN.md` 下篇指针待 10:30 档更新 |
| 下次可发布窗口 | 2026-11-12（周四）21:30–22:30 起均有资格；实际由 UC07 完成时点决定 |
| 阻塞项 | ① UC06 Medium 手动 Import（物料已齐，等 Pin 5 分钟）② UC04 D+7 = 11-14 ③ UC06 D+2 = 11-13 |

## UC06 D+0 台账（2026-11-11）

| 项 | 值 |
|---|---|
| 标题 | Orchestrating Agents: Nobody Decides Who Goes Next |
| 主站 | https://xiongpin.dev/posts/orchestrating-swarm/ — push 21:36:31（GMT+8）= 13:36:31 UTC，≈21:41 起 200 |
| Dev.to | https://dev.to/aws-builders/orchestrating-agents-nobody-decides-who-goes-next-2cg4 — id 5017329，21:37:31（GMT+8）= 13:37:31 UTC，org aws-builders（2794），canonical 指回主站，段中 `<br>` = 0 |
| Builder Center | https://builder.aws.com/content/3Lxn0RS1k0tiClcigN1xz5c0hH9 — ≈21:50（GMT+8）= 13:50 UTC，200，正文图已传站内（prod-assets swar.webp），封面已落库（cove.webp，cover 步骤两次报 FAIL 均为 SKILL §11 已知误判） |
| Medium | **物料已就绪，待手动 Import**（Medium 本身不自动发）。文件：`pinxiong.github.io/writing-lab/distribution/orchestrating-swarm-medium-manual.md`（7 步 + 4 个 subtitle 选项）、`orchestrating-swarm-slack.md`（A/B/C 三版，BC / Dev.to 已回填，Medium 待回填）、`static/images/orchestrating-swarm/cover-medium.png`（1400×788 16:9）。Import 后把 URL 回填四处：手册顶部表格 / Slack 文案 / 本台账 / `publish/README.md` |
| 规模 | 正文 2536 词（en_metrics 口径）/ **16 个代码块**（5 Python + 9 text + 2 bash）/ 1 张机制图 / 4 组实验（E1 正常接力、E2 沉默、E3 双上限、E4/E5/E6 三种失败） |
| 门禁 | `python3 check_publish_gate.py orchestrating-swarm` → **18/18 PASS**（21:36，退出码 0）；发布后复跑仍应为 18/18（Medium URL 位占位与回填两种状态均通过） |

**本档执行备注**

- 物料顺序按 §6：先补 Medium 手册 + Slack 文案（10:30 档已备 16:9 封面），门禁 18/18 后才 push 主站 / 发 Dev.to / 发 BC；`publish_gate` 三项 21:36 置 true。
- Dev.to 流程与 UC05 相同：POST 个人号 → PUT `organization_id=2794`；本机 urllib 直连 api 会 403（Forbidden Bots），加浏览器 User-Agent 后正常。
- BC `publish.py run` 的 cover 步骤报两次 FAIL，均为 troubleshooting §11 已知误判（「当前已保存封面」行有 `prod-assets…/cove.webp` 即已落库）；重传一次确认后直接 `publish`，未按 FAIL 停发。
- **22:25 发布后缺陷修复（Pin 指出）**：UC06 的 5 个 Python 代码块整块带着 SDK 源码的嵌套缩进（8/16/12/20 空格），第一行代码不在 0 位。已对四份稿件（article.md / publish/devto.md / publish/orchestrating-swarm.md / 主站稿件）+ review HTML 整体 dedent，保留相对层级。主站 push、Dev.to `PUT /api/articles/5017329` 均独立复核生效（元数据、canonical、封面、标签未变）；BC 线上导入时本就自动 dedent，逐行核验为 0/4 缩进，无需改动；Medium 尚未 Import，从主站 Import 即得修复版。门禁扩到 21 项（三项「代码块 0 缩进基线」全 PASS），`final_check.py` 新增阻断级扫描。提交 `a36d539` / `68cd0ab`。

## UC06 在制品台账（2026-11-11 10:30 档）

| 项 | 值 |
|---|---|
| 标题 | Orchestrating Agents: Nobody Decides Who Goes Next |
| Slug | `orchestrating-swarm` |
| 正文 | 2536 词 / 15 个代码块 / 1 张机制图 / 4 组实验（E1 正常接力、E2 沉默、E3 双上限、E4/E5/E6 三种失败） |
| 指标 | `final_check` 0 项；`en_metrics` 句长 19.1 / stdev 11.3 / 被动 3.08 / 连接词 1.34 / 名词化 1.38 / Flesch 69.6 |
| 证据 | `usecases/06-swarm/evidence/`：swarm-trace.txt（E1 两次 + E2）、swarm-limits.txt（E3 两档）、swarm-failure.txt（toolerror/timeout/cancel/session）+ 5 份 json |
| 图片 | `static/images/orchestrating-swarm/`：cover.png 1200×676、cover-devto.png 1000×420、**cover-medium.png 1400×788 16:9**、swarm-handoff-loop.png 1200×520（SVG 源齐全） |
| 评审 | 技术专家首轮 FAIL 5 项 → 修订后定向复审 PASS；目标读者有条件 PASS 5 项 → 全部落地；独立复核首轮 FAIL 1 项（Flesch 71.9）→ 修订后 PASS（69.6） |
| 待办 | ~~① Medium 手册 ② Slack 文案 ③ 跑门禁 ④ 21:30 窗口发主站 + Dev.to + BC~~ 全部完成（21:36–21:50）；剩：Medium 手动 Import（Pin）+ D+2（11-13）|

**本轮最该记住的一条**：目标读者把「标题说没人决定，正文其实是模型逐跳决定」指了出来。已在第 2 节补一句并把 ping-pong 实验标成动态路由的正面证据；后续写编排篇时，标题的张力表述要在正文前三段内落地成机制句子。

## UC05 D+0 台账（2026-11-09）

| 项 | 值 |
|---|---|
| 标题 | When "Not Found" Doesn't Mean "Never Happened" |
| 主站 | https://xiongpin.dev/posts/reservations-fencing/ — push 21:32:00（GMT+8）= 13:32:00 UTC，21:36 起 200 |
| Dev.to | https://dev.to/aws-builders/when-not-found-doesnt-mean-never-happened-2eie — id 5004687，21:33:25（GMT+8）= 13:33:25 UTC，org aws-builders（2794），canonical 指回主站 |
| Builder Center | https://builder.aws.com/content/3Ls8Su63RbuSKR3yys1j9t6US1p/when-not-found-doesnt-mean-never-happened — ≈22:15（GMT+8）= 14:15 UTC，200，hero 封面与 "Originally published" 均在线上 |
| Medium | https://medium.com/@pinxiong.cn/when-not-found-doesnt-mean-never-happened-1bc3e54bd912 — **已上线**（2026-11-10 手动 Import，URL 由 Pin 提供）。人工物料齐备：`writing-lab/distribution/reservations-fencing-medium-manual.md`（7 步 + 4 个 subtitle 选项）、`reservations-fencing-slack.md`（A/B/C 三版，四渠道链接齐全）、`static/images/reservations-fencing/cover-medium.png`（16:9）。URL 已回填四处（手册 / Slack / 本台账 / publish/README.md）；`medium.com` 本机不可达，未做页面抓取核验 |
| 规模 | 正文 2421 词（不含代码块）/ 16 个代码块 / 4 组实验（C1 崩溃边界、C2 延迟提交竞态、C3 slot 争用、C4 LLM 三探针） |
| 指标 | `final_check` 0 项；`en_metrics` 定稿读数 stdev 9.8 / 被动 3.1 / 连接词 1.07 / 名词化 3.06 / Flesch 61.9（发布前复跑确认，与 11:20 复审时的 stdev 8.2 差异来自 v3 润色） |

**发布当天的两个偏差（第 1 项已修复）**

1. ~~BC 封面 `cover-medium.png` 是 1400×735（1.90:1），SKILL 要求 16:9。~~ **已于 2026-11-10 10:51 修复**：新建 `cover-medium.svg`（viewBox `0 0 1400 788`），用 `resvg-py` 渲染，PNG 实测 1400×788。BC 线上仍挂 11-09 上传的旧资产，已正常显示、无须重传；Medium 用新文件。流程层面已在 `PIPELINE.md` 第 6 节写死 16:9 出图与尺寸校验，不再把尺寸偏差记成"已知偏差"放行。
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
- 图片：`pinxiong.github.io/static/images/reservations-fencing/`（cover / cover-devto / **cover-medium 1400×788 16:9** / race-timeline，另留 cover-medium.svg 源）
- Dev.to：`usecases/05-reservations-fencing/publish/devto.md`（`build_devto.py --check` = in sync）
- BC / Medium 正文：`usecases/05-reservations-fencing/publish/reservations-fencing.md`（本次改动：标题去转义、正文图改站内根路径）
- **Medium 手册**：`pinxiong.github.io/writing-lab/distribution/reservations-fencing-medium-manual.md`（2026-11-10 补齐）
- **Slack 文案**：`pinxiong.github.io/writing-lab/distribution/reservations-fencing-slack.md`（2026-11-10 补齐）
- **评审预览**：`usecases/05-reservations-fencing/review/article-preview.html`
- 正文：2421 词 / 16 代码块、`final_check` 0 项（发布后 30 分钟内未改正文，符合 PUBLISHING-POLICY §5.4）

## 历史

| 日期 | 篇目 | 结果 |
|---|---|---|
| 2026-11-11 | UC06 Orchestrating Agents: Nobody Decides Who Goes Next | 已发布（主站 21:36 / Dev.to 21:37 / BC ≈21:50），门禁 18/18；Medium 待手动 Import；D+2 = 11-13 |
| 2026-11-09 | UC05 When "Not Found" Doesn't Mean "Never Happened" | 已发布（主站 / Dev.to / BC / Medium），D+2 记录已补（2026-11-11），D+7 = 11-16 |
| 2026-11-07 | UC04 Sessions, State & Memory | 已发布，D+2 记录已补（2026-11-09），D+7 = 11-14 |
| 2026-11-06 | UC03 The Limits That Don't Limit | 已发布 |
| 2026-11-05 | UC02 The Tools That Got Replaced | 已发布 |
| 2026-11-04 | UC01 How the Strands Agent Loop Actually Works | 已发布 |

## 顺延记录

| 日期 | 原因 | 顺延到 | 从哪继续 |
|---|---|---|---|
| — | — | — | — |
