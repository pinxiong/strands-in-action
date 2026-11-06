# UC03 大纲 · Execution Limits（待拍板）

> 系列第 3 篇（Capability 幕第 2 篇，D2）。跨篇依赖：开头一句指明「本文假设你读过 01 的
> 『Thirteen ways to stop』—— 13 种 stop_reason 的四分法已讲过，本篇讲怎么主动制造其中
> 的 `limit_*` 终止」。

## 主线（一句话）

生产事故不是模型变笨，是没设边界 —— 但四个边界各自的粒度和盲区完全不同：**你设的每一道墙，
拦的都不是你以为的东西**（turn 拦的是模型调用不是工具调用；token 上限在单轮回答里根本
不运行；deadline 在同步工具里只是建议）。

## 四个独家发现（实测，别家文章没有）

1. **单轮回答绕过 output token 上限**：检查只发生在轮次边界，`end_turn` 在检查前就结束了
   循环 —— cap=80、实际 255、stop_reason 仍是 `end_turn`（E4-A）。
2. **turn 上限不换算成工具调用上限**：同样 8 次调用，顺序 prompt 用 9 turns、并行 prompt
   用 3 turns（E3）；「一个 turn = 一次模型调用 + 其后的全部工具执行」的源码定义是关键。
3. **deadline 在同步工具里是建议**：5 秒看门狗 + 睡 20 秒的工具 = 21.9 秒才停（E6-B）；
   同样的 cancel() 打在流式上 3.0 秒就停（E6-A）。
4. **total token 是复利**：每轮重读整个对话，输入 434→559→657→755（E5）；四轮就冲破预算。

## 章节草案

1. **The runaway agent you already have** — 无上限跑 8 tick：循环只因工具文本说「完成」
   才停；工具若永远不说，就没有停的条件（E1-A）
2. **What a turn actually is** — 源码定义（types/agent.py:177-178「one model call plus any
   tool execution that follows」）；E3 对比：9 turns vs 3 turns，同一批调用 → turn 上限的
   盲区；E1-B/C：cap 精确生效的样子（limit_turns，工具仍跑完）
3. **The token cap that never runs** — E4-A 单轮绕过 + E4-B 边界拦截（overshoot 9）；
   「soft limit」的源码原话；E5 复利与 limit_total_tokens
4. **The deadline that waits** — E6：3.0s vs 21.9s；agent.cancel 的四个安全点
   （agent.py:680-687）；协作式取消的含义：deadline 要向下游传播
5. **The quota the loop cannot enforce** — turn/token 都拦不住单个工具的调用次数；
   BeforeToolCallEvent.cancel_tool（hooks/events.py:221-247）+ E7：blocked 结果模型能
   读到并改口；循环以 end_turn 自然结束 —— 配额管工具不管循环
6. **Four walls, one priority** — 源码优先级 turns > total_tokens > output_tokens >
   structured_output_attempts（invocation_context.py:229-262）；错字键名/0/True 在跑
   之前就被 TypeError 拦下（E8）
7. **What surprised me** — ① 官方 "Limit Tool Counts" 文档链接是死锚（hooks 页无此节），
   但机制真实存在于 SDK；② DeepSeek 打循环会把工具调用打成文本 DSML（换 nova 的原因，
   也是模型选型即边界选型的一手案例）
8. **When not to use this** / **Try it yourself** / Takeaways

## 取证清单（已完成，evidence/ 留档）

| # | 文件 | 结论 |
|---|---|---|
| turn-limit.txt | 无上限 vs turns=3 vs turns=1 | 9/8/end_turn；limit_turns@3；limit_turns@1 |
| turn-batching.txt | 顺序 vs 并行 prompt | 9 turns vs 3 turns，同 8 调用 |
| turn-granularity.txt | 同 prompt ×5 | 全部 0.9 calls/turn（波动性注记） |
| token-budget.txt | 单轮 vs 工具循环 | 255>80 未拦；109>100 拦下 |
| total-token-budget.txt | 复利 | 434→755 输入增长；2648>2600 |
| cancel-watchdog.txt | 流式 vs 工具内取消 | 3.0s vs 21.9s |
| tool-quota.txt | 配额 hook | 3 试 2 成 1 拦，模型读到 error 并改口 |
| limits-validation.txt | 三个坏 payload | 全部 TypeError，零模型调用 |

## 待用户拍板

1. 标题方向（三选，见发布时另出）
2. 模型口径：全文统一 nova-pro（快且工具调用稳）还是保留 deepseek 对比注记
3. 「DeepSeek DSML 打成文本」要不要进 What surprised me（涉及跨篇口径）
