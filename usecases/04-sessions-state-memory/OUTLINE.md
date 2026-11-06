# UC04 大纲 · Sessions, State & Memory（待拍板）

> 系列第 4 篇（Capability 幕第 3 篇，D3）。跨篇依赖：开头一句指明「本文假设你读过 UC01 的
> 循环剖析 —— 状态 = 一个消息列表、对话是唯一通道。本篇讲这个列表怎么持久化，以及持久化
> 之后模型到底能看见多少」。

## 主线（一句话）

「记忆」不是一件事，是三件事 —— **会话**（消息列表落盘）、**状态**（agent.state）、
**窗口**（模型实际看见的那一段）；三者各自独立成败：重启后它认识你（会话成功），
长对话中它却忘了你（窗口失败），同一条消息两样命运。

## 五个独家发现（全部实测，evidence/ 留档）

1. **持久 ≠ 可见**：FileSessionManager 把 14 条消息全部落盘，但 SlidingWindow(6) 只给模型
   看 6 条 —— codename 在磁盘上活着，在模型眼里死了（E3：stored 2→14 单调涨，
   msgs 从第 4 轮起锁死 6）。
2. **SummarizingConversationManager 没有「窗口大小」**：它根本不在消息数上触发 —— 只在
   context window overflow（reactive）或 projected_input_tokens / context_window_limit
   超过阈值（proactive）时才摘要。第一轮实验 14 条消息全程零摘要，因为它不在乎你有几条
   消息，只在乎你离 300k 窗口有多远（E4 首跑阴性结果，触发公式见源码）。
3. **agent.state 与 conversation_manager_state 同居一个 agent.json**（E2 磁盘解剖），
   非 JSON 值被 ValueError 当场拦下（错误原文拿到）。
4. **两代 session manager 磁盘布局完全不同**：File = 每消息一个 JSON 文件累积
   （message_0..3.json）；Snapshot = 单个 snapshot_latest.json 原地长大（878→1556 字节）。
   同样重启召回，不同的写入模型（E1 vs E5）。
5. **模型遗忘时不认错，编理由**：滑窗丢掉 codename 后，模型不说「我不知道」，而是
   编造隐私理由拒绝回答（E3 两次运行皆然）—— 遗忘在生产环境的真实表现是幻觉，
   不是报错。

## 章节草案

1. **It still knows you after a restart** — E1 双进程实验：进程一植入姓名/数字，进程二
   全新 Agent 凭同一 session id 答出；代码里没有任何东西把事实带过去，只有磁盘文件。
2. **What a session actually writes** — E1 文件树 + agent.json 逐字段解剖（state /
   conversation_manager_state / _internal_state.interrupt_state）；session.json 165 字节
   里有什么。
3. **agent.state: the notebook next to the transcript** — E2：set/get、JSON 强制
   （ValueError 原文）、跨重启恢复；state 与消息的区别：一个是给代码看的，一个是给模型看的。
4. **The window the model actually sees** — E3 完整对照表：stored 14 vs window 6；
   codename 实验；幻觉式拒绝引文；「滑窗管的是模型视野，不是存储」。
5. **Summarize, not drop — but only at the cliff** — E4 两跑：首跑 14 条零摘要（阴性
   结果也是证据）→ 读源码发现触发条件 → 0.005% 阈值武装后摘要真的发生，oldest message
   变成「## Conversation Summary」且 codename 幸存；SDK 警告原文
   "Cannot summarize: only the previous summary is old enough"。
6. **The snapshot rewrite** — E5：SnapshotSessionManager + LocalFileStorage 同题重测；
   两种布局并排；save_latest_on 的 message/invocation/trigger 三档；为什么新 API 走向
   单文件快照（标注为推断）。
7. **What surprised me** — ① 遗忘表现为幻觉式拒绝而非报错；② Summarizing 的触发条件
   与名字暗示的完全不同；③ File 与 Snapshot 的目录哲学差异。
8. **When not to use this** / **Try it yourself** / Takeaways（三件事各自一句话）

## 标题候选

| # | 标题 | 优点 | 缺点 |
|---|---|---|---|
| A | **The Memory That Isn't One Thing** | 直接点题主线；短 | 没有数字/画面感 |
| B | **It Remembers Across Restarts — and Forgets Mid-Conversation** | 反差张力最强，剧透了核心发现 | 偏长（60 字符） |
| C | **Your Agent Remembers Everything and Sees Almost Nothing** | 「记得一切却几乎看不见」精准概括发现 1 | 略抽象 |
| D | **Three Kinds of Memory, One Missing Codename** | 有故事钩子（codename 实验） | 三记忆提法与正文顺序需对齐 |

个人推荐 B（张力风格延续 UC02/UC03 的传统），A 作副标题候选。

## 取证清单（已完成）

| 文件 | 内容 | 关键数字 |
|---|---|---|
| evidence/session-restart.txt | E1 双进程 File 持久化 | 4 个 JSON 文件；跨进程答出 Pin/42 |
| evidence/agent-state.txt | E2 state 读写 + 重启 | ValueError 原文；visits=1 跨进程存活 |
| evidence/agent-state-on-disk.json | agent.json 完整解剖 | state + conversation_manager_state 同文件 |
| evidence/sliding-window.txt | E3 滑窗遗忘 | stored 2→14 / msgs 锁 6 / ORION_VISIBLE=False |
| evidence/summarizing-window.txt | E4 摘要幸存 | 摘要消息成 oldest；ORION 幸存；SDK 警告原文 |
| evidence/snapshot-session.txt | E5 快照版重启 | snapshot_latest.json 878→1556 字节 |

## 待实验补充（可选，大纲拍板后决定）

- S3SessionManager / AgentCore Memory：本篇按覆盖矩阵只点到（LTM 属 AgentCore 交叉引用，
  不做实测），如要实测需云资源，建议留到 UC08 或加框注。
