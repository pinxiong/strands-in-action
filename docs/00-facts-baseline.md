# Strands Agents 事实基线

> 抓取日期：**2026-10-21**。每条事实带来源 URL。未证实的明确标注。
> 这是 `strands-in-action` 系列的**输入**：写文章时只能用这里有的事实，或跑出来的数字。

---

## 1. 是什么

| 项 | 事实 | 来源 |
|---|---|---|
| 定位（README 副标题） | "A model-driven approach to building AI agents in just a few lines of code." | [harness-sdk](https://github.com/strands-agents/harness-sdk) |
| 定位（网站 H1，更新的口径） | "The open source toolkit for building production agents." | [strandsagents.com](https://strandsagents.com/) |
| 开源时间 | 2025-05-16，AWS Open Source Blog，作者 Clare Liguori | [aws.amazon.com/blogs/opensource](https://aws.amazon.com/blogs/opensource/introducing-strands-agents-an-open-source-ai-agents-sdk/) |
| PyPI 首个版本 | `0.0.1` 上传于 2025-05-14 | [PyPI JSON](https://pypi.org/pypi/strands-agents/json) |
| 许可证 | Apache License 2.0 | PyPI / npm 元数据 + `LICENSE.APACHE` |
| 名字由来 | "Like the two strands of DNA, Strands connects two core pieces of the agent together: the model and the tools." | 同上 AWS 博客 |

### 1.1 仓库现状（★ 易踩：名字变了）

- **主仓库已改名**：`strands-agents/sdk-python` → **`strands-agents/harness-sdk`**（301 重定向）。
  `sdk-typescript` 已**归档**，TS 代码 2026-04 起合入 monorepo 的 `strands-ts/`。
- star 数（GitHub API，2026-10-21）：harness-sdk **8877**、tools 1332、agent-sop 1193、
  samples 912、agent-builder 431（已归档）、sdk-typescript 695（已归档）、box 448、
  evals 238、shell 276（Rust）、devtools 17。
- monorepo 目录：`harness-py/`、`harness-ts/`、`strands-cli/`、`strands-py/`、
  `strands-ts/`、`strands-mcp/`、`site/`、`team/`、`test-infra/`。
- **写文章时所有 GitHub 链接必须指向 `harness-sdk`**，指 `sdk-python` 虽然能跳转但会显得过时。

### 1.2 设计哲学（官方原话，可直接引用）

> "Compared with frameworks that require developers to define complex workflows for their
> agents, Strands simplifies agent development by embracing the capabilities of
> state-of-the-art models to plan, chain thoughts, call tools, and reflect."
> — AWS Open Source Blog, 2025-05-16

> "In a model-driven approach, the agent uses the model to dynamically direct its own steps
> and to use tools in order to accomplish the specified task."
> — 同上

> "What Strands deliberately does not add is a platform. It runs in your own process as a
> library, with no hosted control plane, scheduler, or database to stand up first."
> — [choosing-an-agent-foundation](https://strandsagents.com/docs/user-guide/migrate/choosing-an-agent-foundation/)

> ⚠️ **别写错的一句话**：官方说 "The loop is a few dozen lines" 指的是**你自己手写的那个
> while 循环**，不是 Strands 源码的 loop 行数。Strands 自身 loop 源码行数官方未给数字
> （**未证实**）。

### 1.3 最小示例（README 原文）

```python
from strands import Agent
from strands_tools import calculator
agent = Agent(tools=[calculator])
agent("What is the square root of 1764")
```

```typescript
import { Agent } from '@strands-agents/sdk'
const agent = new Agent()
const result = await agent.invoke('What is the square root of 1764?')
```

**默认参数（源码实证）** — [bedrock.py](https://raw.githubusercontent.com/strands-agents/harness-sdk/main/strands-py/src/strands/models/bedrock.py)

- 默认 provider = `BedrockModel`
- `DEFAULT_BEDROCK_MODEL_ID = "global.anthropic.claude-sonnet-4-6"`
- `DEFAULT_BEDROCK_REGION = "us-west-2"`（解析顺序：`region_name` → boto session → `AWS_REGION` → `us-west-2`）

> ⚠️ **本机 CLI 默认区域实测是 `us-east-1`**（2026-11-01 `aws configure get region`），
> 与文档默认的 `us-west-2` 不同。Strands 的解析顺序是 `region_name` → boto session →
> `AWS_REGION` → `us-west-2`，所以实际生效的是 boto session 读到的那个值。
>
> ★ **好消息：默认 region 不用猜。** Strands 在报错时会自己打印解析结果：
> ```text
> └ Bedrock region: us-east-1
> └ Model id: global.anthropic.claude-sonnet-4-6
> ```
> 出处：`usecases/01-the-loop/evidence/11-default-deepseek.txt`。UC01 的核心 takeaway 之一。

---

## 2. 版本与发布时间线

| 包 | 最新（2026-11-01 PyPI 实测） | 本系列实测锁定 | 运行时要求 |
|---|---|---|---|
| Python `strands-agents` | **1.63.0**（2026-10-30） | **1.61.1**（升级受网络限制未完成） | Python ≥ 3.10 |
| TypeScript `@strands-agents/sdk` | 1.21.0 | — | Node ≥ 22 |
| `strands-agents-tools` | **0.8.11**（2026-10-30） | **0.8.9** | — |
| `strands-agents-evals` | **1.8.0**（2026-10-30） | 未装 | — |

> **发版节奏 ≈ 每周一个 minor**：1.60.0(10-12) → 1.61.0(10-14) → 1.61.1(10-15) →
> 1.62.0(10-21) → 1.63.0(10-30)，18 天内 5 个版本。
> **对策**：每篇顶部标 `verified on <日期> · strands-agents <版本>`；每写一篇时把版本刷到
> 最新并重跑证据；A0 概览篇维护版本对照表。详见 PLAN 第 9 节风险表。

**里程碑**

- 0.0.1（2025-05-14）→ **1.0.0 GA（2025-07-15）**：新增 A2A 协议 + 4 个多智能体原语
  （agents-as-tools / handoffs / swarms / graph）+ 5 个合作方 provider —
  [Introducing Strands Agents 1.0](https://aws.amazon.com/blogs/opensource/introducing-strands-agents-1-0-production-ready-multi-agent-orchestration-made-simple/)
- TypeScript 预览宣布 2025-12（AWS What's New，同期宣布边缘设备支持 GA、steering 实验特性、评估预览）
- TypeScript **v1.0.0 GA 2026-04-30**
- 双向流式 **2026-10 GA**
- 2026-10 新增 `strands-harness` / `@strands-agents/harness`（`create_harness()` / `createHarness()`）
- 2026-10-02 新建 `box` 仓库（容器 + Dogwood 策略的 agent 沙箱，预览）
- **CNCF / Linux Foundation 捐赠：未证实。** 只有第三方报道称 Amazon 于 2026-08 加入
  LF 旗下 Open Secure AI Alliance 并"贡献 Strands Agents"，非官方源，不要用。

---

## 3. 与 AWS 的关系

- **是 AWS 官方开源项目**，AWS 内部已在生产使用：
  > "Multiple teams at AWS already use Strands for their AI agents in production,
  > including Amazon Q Developer, AWS Glue, and VPC Reachability Analyzer."
  > — AWS Open Source Blog, 2025-05-16
- **AgentCore Runtime 官方把 Strands 列为支持的开源框架之一**（与 CrewAI / LangGraph /
  LlamaIndex / Google ADK / OpenAI Agents SDK 并列）—
  [AgentCore devguide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- **`agentcore create` 向导把 Strands 标为 "(recommended)"** —
  [CLI get started](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-get-started-cli.html)
- AgentCore Memory 同样支持 Strands。
- **AWS 是否提供商业支持 / SLA：未证实。**

### 3.1 与 AgentCore 的分工（系列要讲清楚的那条线）

| | Strands Agents | Bedrock AgentCore |
|---|---|---|
| 形态 | 库 / SDK，跑在你的进程里 | 托管服务 |
| 你得到什么 | agent loop、tools、多 agent 原语、trace | Runtime、Memory、Gateway、Identity、Policy、Evaluations、Registry |
| 控制面 | 无（"a library, not a platform"） | 有 |
| 关系 | Strands agent 可以部署到 AgentCore Runtime | AgentCore 不挑框架，Strands 只是其一 |

---

## 4. 能力矩阵

### 4.1 Agent 构造

`Agent.__init__` 参数（[API 参考](https://strandsagents.com/docs/api/python/strands.agent.agent/)）：
`model, messages, tools, system_prompt, structured_output_model, callback_handler,
conversation_manager, record_direct_tool_call, load_tools_from_directory, trace_attributes, *,
baggage_attributes, aux_model, agent_id, name, description, state, context_manager, plugins,
hooks, interventions, session_manager, memory_manager, structured_output_prompt, tool_executor,
retry_strategy, concurrent_invocation_mode, checkpointing, sandbox, storage, background_tasks`

- 默认 `model` = `BedrockModel`；默认 `conversation_manager` = `SlidingWindowConversationManager`
- **`max_parallel_tools` 已不在当前构造函数里**（老资料会提到，别写）
- 调用：`agent(prompt)` / `await agent.invoke_async(prompt)` → `AgentResult`
  （`stop_reason` / `message` / `metrics` / `state` / `structured_output`）
- `agent.structured_output(PydanticModel, prompt)`
- `async for event in agent.stream_async(prompt)`

### 4.2 工具

- `@tool` 装饰器：**函数 docstring 即工具描述**，类型注解生成 JSON schema；
  `tool_context: ToolContext` + `@tool(context=True)` 拿上下文；支持 async / async generator。
- `strands-agents-tools`（0.8.9）约 **52 个工具**：file_read / file_write / editor、
  python_repl、shell、http_request、current_time、calculator、use_aws、retrieve、journal、
  think、stop / speak、mem0_memory、image_reader、generate_image、nova_reels、
  code_interpreter、browser、use_computer、swarm、workflow、graph、a2a_client、
  agent_core_memory、cron、sleep、environment、load_tool、handoff_to_user、use_llm、slack、tavily_*、exa_* …
- ★ **2026 重大变化：24 个工具已标记 deprecated**，迁移到 SDK 内置 `strands.vended_tools`
  （shell、sleep、notebook、http_request、handoff_to_user 等），`strands-agents-tools`
  **仓库计划归档**。这是**独家时效素材**，写一篇"工具层正在换血"很有价值。
- ★★ **实测原文（2026-11-01，本系列独家一手证据）**：`calculator` 被调用时直接打印
  ```text
  DEPRECATION WARNING: calculator is deprecated. This warning becomes an error log
  in v0.9.0. To achieve similar functionality, use the shell tool vended by
  strands-agents (from strands.vended_tools import shell). This does change the
  security boundary: calculator only ever evaluated an expression checked against
  an AST allowlist, while shell executes arbitrary commands, so review it against
  your threat model before switching.
  ```
  **关键**：官方建议的替代品 `shell` **改变了安全边界**（AST 白名单 → 任意命令执行）。
  这不是等价替换，写 UC02 时必须点破。出处 `evidence/13-tools-deepseek.txt`。
- MCP：`MCPClient`，三种 transport（stdio / Streamable HTTP / SSE），必须在
  `with mcp_client:` 上下文里 `list_tools_sync()`。SDK 兼容 mcp 1.x 与 2.x。
  ⚠️ **基线内部矛盾待解决**：本节说必须用 `list_tools_sync()`，而第 7 节又说 mcp 2.x
  移除了该同步 API。写 UC02 时必须实测确定当前版本下哪种写法有效，不要照抄基线。

### 4.3 多 agent（四种范式）

| 范式 | API | 关键参数 |
|---|---|---|
| **Swarm** | `Swarm(nodes=[...], entry_point=...)` | `max_handoffs=20`、`max_iterations=20`、`execution_timeout=900.0`、`node_timeout=300.0`；注入 `handoff_to_agent` 工具 + `SharedContext` |
| **Graph** | `GraphBuilder().add_node().add_edge(condition=fn)` | `set_max_node_executions()`、`set_execution_timeout()`、`set_node_timeout()`、`reset_on_revisit()`；结果含 `execution_order` |
| **Workflow** | 无独立 Python 类；用 `workflow` 工具或手写顺序编排 | — |
| **A2A** | `A2AAgent(url, agent_card_path=...)` + 服务端 `A2AServer` | agent card 默认 `/.well-known/agent-card.json`；Swarm 不支持 A2A |

### 4.4 状态与会话

- Session manager：`SnapshotSessionManager`（新推荐，配 Storage 后端）、
  `FileSessionManager`（默认 `~/.strands/sessions/`）、`S3SessionManager`、自定义 `SessionRepository`
- AgentCore Memory：`AgentCoreMemorySessionManager(agentcore_memory_config=AgentCoreMemoryConfig(...))`，
  LTM 三策略 summary / userPreference / semantic，namespace 形如 `/strategies/{id}/actors/{actorId}`
- Conversation manager：`SlidingWindowConversationManager`（默认）、
  `SummarizingConversationManager(summary_ratio=0.3, preserve_recent_messages=10)`、`NullConversationManager`
- Agent state：`agent.state.set/get/delete`，强制 JSON 可序列化，session 持久化后跨重启恢复
- **fork / branch 会话：未证实**

### 4.5 可观测与评测

- OTel span 层级：**Agent → Cycle（含 `event_loop.cycle_id`）→ LLM → Tool**；
  属性 `gen_ai.usage.prompt_tokens` / `completion_tokens` / `total_tokens` / cache tokens / `gen_ai.tool.name`
- `from strands.telemetry import StrandsTelemetry; StrandsTelemetry().setup_otlp_exporter()`
- CloudWatch / X-Ray 走 ADOT collector（需开 Transaction Search）；Langfuse 等走 OTLP endpoint
- `strands-agents-evals`（1.6.0）：output 类 OutputEvaluator / TrajectoryEvaluator /
  InteractionsEvaluator；trace 类 ToolSelectionAccuracy、ToolParameterAccuracy、Helpfulness、
  Faithfulness、Coherence、Conciseness、ResponseRelevance、Harmfulness、Refusal、
  Stereotyping、InstructionFollowing、GoalSuccessRate；另有 5 个多模态 + 3 个 Skill + 3 个 chaos。
  概念 = `Case(name, input, expected_output, metadata)` + `Experiment(cases, evaluators).run_evaluations(fn)`；
  CLI：`strands-evals run/validate/report/diagnose/generate`；Red Team 策略 Crescendo / GOAT / PAIR / BadLikertJudge / SequentialBreak。

### 4.6 其他机制

- **Hooks**：`BeforeInvocationEvent` / `AfterInvocationEvent` / `MessageAddedEvent` /
  `BeforeToolCallEvent` / `AfterToolCallEvent` / `BeforeModelCallEvent` / `AfterModelCallEvent`；
  多 agent 另有 `BeforeNodeCallEvent` / `AfterNodeCallEvent`。
  可改写：`event.cancel_tool`、`event.selected_tool`、`event.result`、`event.cancel_node`；
  `HookOrder.SDK_FIRST / DEFAULT / SDK_LAST`。
- **Structured output**：Pydantic `BaseModel`，实现为 schema→tool spec（tool-based），
  结果在 `result.structured_output`，校验失败抛 `StructuredOutputError`。native 模式**未证实**。
- **Guardrails**：`BedrockModel(guardrail_id=..., guardrail_version=..., guardrail_trace=...)`，
  触发后 `stop_reason == "guardrail_intervened"`，输入默认改写（`guardrail_redact_input`），
  输出改写默认关；shadow 模式用 hooks + ApplyGuardrail API。
  PII：SDK 自身不做遥测脱敏，官方建议 LLM Guard / Presidio / Langfuse mask 或 OTel Collector 层处理。
- **HITL**：interrupt / resume —— 工具内 `tool_context.interrupt(name, reason=...)` 或 hook 内
  `event.interrupt(...)`；agent 以 `stop_reason == "interrupt"` 暂停，`result.interrupts` 列出待答项，
  用 `{"interruptResponse": {"interruptId": ..., "response": ...}}` 恢复；
  另有开箱即用的 `HumanInTheLoop` intervention handler（默认 `ask="stdio"`）。

---

## 5. 部署目标（官方 6 个）

来源：[Operating Agents in Production](https://strandsagents.com/docs/user-guide/sdk/deploy/operating-agents-in-production/)

| 目标 | 官方定位原话 |
|---|---|
| **Bedrock AgentCore** | A secure, serverless runtime for deploying and scaling dynamic AI agents and tools |
| **AWS Lambda** | Serverless option for short-lived agent interactions and batch processing |
| **AWS Fargate** | Containerized deployment with streaming support, ideal for interactive applications |
| **AWS App Runner** | Containerized + streaming + automated deployment, scaling, load balancing |
| **Amazon EKS** | Containerized + streaming, ideal for interactive / high-concurrency |
| **Amazon EC2** | Maximum control and flexibility for high-volume or specialized infrastructure |

### 5.1 官方生产清单（★ 可直接作为一篇文章的骨架）

**生产配置**：显式配置 model 与 tools，**不要依赖默认值**；显式列出工具、
保持自动工具加载关闭（默认即关）、定期审计工具使用。

**安全**：① 工具最小权限 ② 输入校验 ③ 输出脱敏（用 guardrails 做自动化）。

**执行边界（四个独立维度，官方原话：a useful baseline covers four independent dimensions）**

1. **Agent loop iterations** — 传 `limits`（两个 SDK 同名），限制模型+工具的循环轮次
2. **Tool invocations** — 给昂贵/限流/有副作用的工具加配额（Limit Tool Counts hook）
3. **Token consumption** — invocation 级 total/output token 上限 + 模型 `maxTokens`；
   ⚠️ invocation token 限制是**在轮次之间检查**，单次模型调用可能超额后才停
4. **Wall-clock time** — 在 invocation 外面设 deadline 并 cancel；Python `agent.cancel()`，
   TS 传 `cancelSignal`（如 `AbortSignal.timeout(30_000)`）或 `agent.cancel()`；
   ⚠️ 对已经在工具里跑起来的工作，取消是**协作式**的，deadline 要向下游传播

> "Do not rely on only one boundary. For example, a turn limit does not constrain a single
> slow tool, while a timeout alone does not provide a predictable token budget."

**多 agent 安全边界**：Swarm 用 `maxSteps` / `timeout` / `nodeTimeout`（TS）或对应 Python 参数；
Graph 用 `set_max_node_executions` / `set_execution_timeout` / `set_node_timeout`。

**监控四信号**：① 工具执行时间与错误率 ② token 用量 ③ 端到端响应时间 ④ 错误率。

---

## 6. samples 仓库（用户指定参考）

[github.com/strands-agents/samples](https://github.com/strands-agents/samples) — 912 stars

> 官方声明："The examples in this repository are for **demonstration and educational
> purposes** only … **not intended for direct use in production**."

Python 八类：

| 目录 | 内容 |
|---|---|
| `01-learn` | SDK 教程：基础、多 agent、流式 |
| `02-deploy` | Lambda / Fargate / AgentCore 部署模式 |
| `03-integrate` | AWS 服务、数据库、第三方工具集成 |
| `04-industry-use-cases` | 金融、医疗、零售、生产力等行业应用 |
| `05-technical-use-cases` | 架构模式，含 Agentic RAG |
| `06-evaluate` | 评测教程与测试模式 |
| `07-ux-demos` | 带 UI 的全栈应用 |
| `08-edge` | 边缘设备，含 physical AI 与机器人 |

TypeScript 两类：`01-learn`、`02-deploy`（AgentCore）。

---

## 7. 已知坑（社区真实反馈，可作为 "What surprised me"）

| 坑 | 细节 | 来源 |
|---|---|---|
| **mcp 1.x vs 2.x** | 2.x 移除 `list_tools_sync` 同步 API、`tool_result_content` 结构变化、工具名前缀规则改变；升级后报错静默 | SDK 文档 / GitHub issue |
| **工具层换血** | 24 个工具 deprecated，`strands-agents-tools` 计划归档，迁到 `strands.vended_tools` | PyPI / 文档 |
| ~~**Bohr token 空间暴涨 5 倍**~~ | ⛔ **无源，禁止引用**。2026-11-01 复核未找到任何出处，疑为早期调研的误记 | 无 |
| **`journal` 工具崩溃** | ⚠️ 来源标注为"社区案例"但**无 URL**，引用前必须复核 | 待补 |
| **Bedrock 默认 5 分钟超时** | ⚠️ 同上，**无 URL**，引用前必须复核 | 待补 |
| **`shell` / `python_repl` 执行任意代码** | 生产必须禁用或进沙箱 | 常识 + 官方最小权限建议 |
| **文档默认 region 是 `us-west-2`，实际不是** | 本机 boto session 解析出 `us-east-1`。Strands 会自己打印 `└ Bedrock region:` | 源码 + 2026-11-01 实测 |
| **循环次数不确定（实测）** | 同一问题问 3 次：2 轮 / 2 轮 / 3 轮，token 3233→5022。断言必须写 `>=2` 不能写 `==2` | `evidence/13`、`14` |
| **DeepSeek 延迟远高于 Nova（实测）** | 同代码同问题：deepseek.v3.2 ≈ 18.0s，amazon.nova-pro-v1:0 ≈ 1.4s，token 数只差 5% | `evidence/15-model-swap.txt` |
| **推理模型的 `text` 为 `None`（实测）** | `us.deepseek.r1-v1:0` 花了 790 output tokens 但 `message.content[0].text` 是 `None`（输出在 reasoning 块） | 2026-11-01 实测 |

---

## 8. 本机环境（2026-11-01 实测）

| 项 | 值 |
|---|---|
| AWS 账号 | `123456789012`（**已脱敏**：公开仓库不写真实账号 ID），`sts get-caller-identity` 通过 |
| CLI 默认区域 | **`us-east-1`**（`aws configure get region` 实测；与 Strands 文档默认的 `us-west-2` 不同） |
| Bedrock us-east-1 | 可达；provider 分布 Amazon 21 / Anthropic 15 / OpenAI 14 / Mistral 13 / Meta 7 / Qwen 5 / NVIDIA 4 / DeepSeek 2 等 |
| **可用的 DeepSeek model id** | `deepseek.v3.2`（ON_DEMAND，可直接调用）；`us.deepseek.r1-v1:0`（推理配置，ACTIVE）；`deepseek.r1-v1:0`（INFERENCE_PROFILE） |
| Python | 3.11.9（managed），`uv` 在 `~/.local/bin/uv` |
| Docker | 未安装（影响：Container / box 相关实验走不了） |
| PyPI 访问 | `pip` 解析 `boto3` 失败（`from versions: none`，网络问题）；`uv` 可用。写文档时优先给 `uv` 命令 |
