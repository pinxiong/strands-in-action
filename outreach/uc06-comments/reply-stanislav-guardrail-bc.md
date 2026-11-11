Thanks Stanislav — you are pointing at two different failures in one trace, and I do not think any single one of the three placements covers both. I ran a deterministic follow-up probe with a scripted model (no LLM, strands-agents 1.63.0, one model call = 100 input + 20 output = 120 tokens) to see what each guardrail can actually observe. Probe and raw output: https://github.com/pinxiong/strands-in-action/tree/master/outreach/uc06-comments

First, a qualifier to my own article. The zero in the article is SwarmResult.accumulated_usage, which only sums nodes that produced a result record (swarm.py:1082-1084). It is not the SDK's request-level usage. In the probe, a node whose model call finished and whose tool then blocked past node_timeout gives:

CASE timeout_tool
  status: "failed"
  node_history: []
  execution_count: 0
  before_node_events: ["calculator"]
  boundary_rows: [{"hook_invocation_context": "None", "node": "calculator", "swarm_totalTokens": 0}]
  model_calls: 1
  swarm_totalTokens: 0
  request_totalTokens: 120
  node_result_usage: "no node result"

So result.invocation_context.usage recovers that 120 after the run. But when the timeout lands during the model stream itself, both counters the caller can read stay at zero:

  model_calls: 1
  swarm_totalTokens: 0
  request_totalTokens: 0
  node_result_usage: "no node result"

That is the case where provider-side data is the only source of truth I can point to. I did not enable Bedrock model invocation logging or query CloudWatch in this bench, so the reconciliation part below is a design recommendation, not a measured result.

On the three placements:

1) A token budget in BeforeNodeCallEvent is a coarse kill switch between nodes, not a budget. In a three-node run the hook saw 0, 240 and 480 at the three boundaries; the event's invocation_context field is None on this path in 1.63.0 (swarm.py:853 constructs it with source, node_id and invocation_state only), so the only counter the hook can read is source.state.accumulated_usage — the same one that reads zero after a timeout. It also cannot preempt a node that is already running (there is an explicit TODO for a cancellation token at swarm.py:856), and it fires once per node turn: in CASE repeat, four save_draft calls happened inside one turn with before_node_events: 1. Setting cancel_node did stop the third node (CASE node_cancel, status failed, node_history ["researcher", "calculator"]), so it works as a circuit breaker. It does not meter spend.

2) A dedicated validator node is not guaranteed to run. In CASE silent, the entry node ended without a handoff:

  status: "completed"
  node_history: ["researcher"]
  validator_status: "never ran"

The same silence that ends the job also skips the validator, and a validator node is itself another model call. I would put the acceptance check in the caller after stream_async returns, where it is deterministic and costs no tokens. If you keep a validator node, assert in the caller that it appears in node_history.

3) For the eleven save_draft calls, the useful in-process hook is BeforeToolCallEvent.cancel_tool, which fires per tool call rather than per node. CASE repeat_cap cut four attempted calls down to two real executions:

  model_calls: 5
  tool_call_events: 4
  tool_calls_cancelled: 2
  save_draft_executions: 2
  save_draft_ledger: ["save_draft:v1", "save_draft:v2"]
  swarm_totalTokens: 600
  request_totalTokens: 600

Cancelling a tool stops duplicate writes, not the token burn. It is an idempotency guard, not a budget.

There is a fourth option inside the SDK: request-level limits on a parent Agent call (total_tokens, output_tokens, turns). CASE agent_limits stopped with stop_reason "limit_total_tokens" after two model calls and 240 tokens against a 150 cap:

CASE agent_limits
  stop_reason: "limit_total_tokens"
  model_calls: 2
  save_draft_executions: 2
  request_totalTokens: 240

The SDK calls these soft limits, checked before each turn, so tools requested by the previous turn still finish. Graph and Swarm have no limits option of their own: CASE swarm_limits_kw passed limits={"total_tokens": 150} to Swarm.stream_async and all three nodes still ran to 600 tokens. The supported path is to start a limited Agent request and pass its invocation_context into the swarm; I verified the Agent side and the ignored kwarg, but did not wire that nested path end to end.

So the short version: tool-level cancellation for duplicate writes, request-level limits for an in-process soft budget, an acceptance check outside the swarm, and provider-side accounting for what was billed. For that last layer, Bedrock model invocation logs carry input.inputTokenCount and output.outputTokenCount with requestId and identity.arn, plus caller-supplied requestMetadata when you provide it (https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html — logging is disabled by default and needs an S3 or CloudWatch Logs destination). CloudWatch publishes InputTokenCount and OutputTokenCount under the AWS/Bedrock namespace with a ModelId dimension (https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-runtime-metrics.html); those are aggregate metrics for alarms, not per-invocation records. I do not currently have a way to attribute a log row to one swarm run without a per-run tag in requestMetadata or a captured requestId, and I have not tested either wiring through Strands.

And yes: I have added this to the graph follow-up's checklist. Explicit edges give a deterministic place to put a budget check and a validator, but I will not assume they fix accounting — I will measure the same counters against the same fixture and report what the graph actually changes.

Scope: offline scripted model, four save_draft calls standing in for the eleven real ones, a fixed 120 tokens per model call, and one node_timeout value (0.25s). No real Bedrock calls, no CloudWatch queries, no nested limits wiring, and no test of a tool that wrote a side effect before the timeout.
