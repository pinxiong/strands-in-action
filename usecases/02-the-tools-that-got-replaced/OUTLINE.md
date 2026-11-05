# UC02 大纲 · The Tools That Got Replaced（待拍板）

> 系列第 2 篇（Capability 幕首篇，D2）。跨篇依赖：开头一句指明「本文假设你读过 01 的
> 『What the model sees on the next turn』—— 工具结果如何回传已讲过，本篇讲工具如何被描述」。

## 主线（一句话）

你写的 `@tool` 函数只有几行，但模型看到的是一份**用 docstring 写成的契约** —— 而 AWS 正在把
37 个内置工具连锅端掉，旧工具和新工具的差别不只是位置，是安全边界。

## 两个独家钩子（别家文章没有的）

1. **弃用清单在长大**：`strands-agents-tools` 里带 `_DEPRECATION_MESSAGE` 的模块，
   2026-10-21 基线是 24 个，2026-11-04 实测 **37 个**，v0.9.0 全部变 import error。
2. **description 提取的反直觉实现**（decorator.py:235-283）：Args 段被**手写行扫描**切掉，
   但 Returns / Examples / Raises 段**原样保留**进 description 发给模型 —— 你的示例代码
   会直接出现在模型的上下文里。

## 场景设计（合并能力，不照抄 samples）

一个「仓库巡检 agent」逐步长出手：

- **T1 自定义 `@tool`**（纯函数：统计目录代码行数）→ 展示 docstring→schema 全链路
- **T2 带类型注解/默认值/Annotated 的 `@tool`** → 展示 Pydantic 校验拦截坏参数
- **T3 vended tool**（`shell` 或 `file_read`）→ 展示新旧工具层与安全边界
- **T4 MCP 工具**（本地 stdio 起一个 server）→ 展示三种 transport 与自动探测

## 章节草案

1. **The smallest tool that works** — T1 跑起来（跨篇依赖句在这里）
2. **What the model actually receives** — 打印 ToolSpec：name / description / inputSchema（E1 取证）
3. **The three-way extraction, in the source** — decorator.py:80 签名 + type_hints + docstring_parser；Pydantic create_model（:193-233）
4. **The Args section gets cut, the rest does not** — :235-283 行扫描逻辑 + E2 取证（Examples 出现在模型上下文）
5. **Your docstring is a prompt** — E3：同函数两份 docstring（清晰 vs 误导），模型行为分叉
6. **Where bad parameters die** — Pydantic 校验在模型与函数之间拦截（E4）
7. **Thirty-seven tools are being replaced** — 弃用清单 24→37 实测；双通道警告（IDE @deprecated + 运行时 logger.warning，calculator.py:792-906）；vended_tools 全景
8. **The security boundary moved** — calculator（AST 白名单）→ shell（任意命令）：不是平替，怎么选
9. **MCP: one client, three transports** — stdio/sse/streamable-http 自动探测（mcp_client.py:244-246）+ E5 本地 server 实测
10. **Structured output is a tool in disguise** — schema→tool 转换，呼应 01 的 forced retry（event_loop.py:435）
11. **What surprised me** / **When not to use this** / **Try it yourself** / Takeaways

## 取证计划（evidence 先行，E1-E5）

| # | 实验 | 产出 |
|---|---|---|
| E1 | 打印 T1 的 ToolSpec | docstring→schema 的完整对照 |
| E2 | 带 Examples 段的 docstring → spec | 反直觉细节证据 |
| E3 | 两份 docstring 的模型行为 | docstring 即 prompt 的直接证据 |
| E4 | 模型传错类型 → 拦截日志 | Pydantic 校验位置 |
| E5 | stdio MCP server + agent 调用 | transport 实测 |

## 拍板（2026-11-04）

1. 场景：**仓库巡检**（推荐项，用户未另选）
2. T3：**shell**（推荐项，安全边界冲突强，呼应 UC01 伏笔）
3. MCP：**本地 stdio server**（用户拍板，零外部依赖）
