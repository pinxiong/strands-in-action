# UC01 · The Loop

Run the smallest Strands agent that works, then follow the loop down into the SDK source
and back up again with logs that agree with it.

This is the first article in the *Strands in Action* series. The narrative lives in
[`article.md`](article.md); this file holds the commands. The article starts from the
pinned agent; `01_default.py` below is the control experiment that shows what an unpinned
`Agent()` resolves to, and why the walkthrough pins its model.

---

## 1. What you will see when you finish

Eight scripts. Four of them read the loop itself out of the SDK rather than out of the docs.

| Script | Expected result |
|---|---|
| `01_default.py` | fails with a `ValidationException` about Anthropic geo-restriction |
| `02_pinned.py` | one cycle, one answer, 27 tokens |
| `03_tools.py` | two or three cycles, one or two `calculator` calls, 3000 to 5000 tokens |
| `04_trace.py` | the OpenTelemetry span tree with `parent_cycle_id` links |
| `05_recursion.py` | the loop as Python stack depth, one indented line per cycle |
| `06_cycle_ids.py` | `event_loop_cycle_id` and `event_loop_parent_cycle_id` per turn |
| `07_tool_schema.py` | the exact tool spec the model receives, 5500 characters for one tool |
| `08_defaults.py` | the resolved region and model, with no API call |
| `09_messages.py` | the shape of the conversation the model sees on each turn |

The cycle counts are ranges on purpose. The model decides how many turns it takes, so the
same script gives 2 cycles on most runs and 3 on some.

The first failure is deliberate. It is the fastest way to see which defaults the SDK chose
for you.

## 2. Independence and difficulty

**Difficulty: D1.** One capability (the agent loop), under 30 minutes, no AWS resources
created beyond Bedrock model invocations.

This use case is self-contained. You do not need any other use case, you do not need Docker,
and you do not need infrastructure. You do need a model that your account and your location
can actually invoke, which is why step 4 asks you to check that first.

## 3. Prerequisites

- Python 3.10 or newer (verified on 3.11)
- AWS credentials with `bedrock:InvokeModel` and `bedrock:ConverseStream` permission
- A default region that can reach Bedrock (this walkthrough uses `us-east-1`)
- No MCP server, no Docker, no deployed runtime

## 4. Check which models you can actually call

This step comes first because it is the thing that breaks. Listing models is not the same as
being allowed to invoke them.

```bash
aws bedrock list-foundation-models --region us-east-1 \
  --query 'modelSummaries[].{id:modelId,provider:providerName}' --output text \
  | grep -i deepseek
```

Expected output on an account with DeepSeek enabled:

```text
deepseek.r1-v1:0     DeepSeek
deepseek.v3.2        DeepSeek
```

`deepseek.v3.2` supports on-demand invocation, so it needs no inference profile. That is why
this walkthrough uses it. Confirm you can invoke it before continuing:

```bash
aws bedrock converse --region us-east-1 --model-id deepseek.v3.2 \
  --messages '[{"role":"user","content":[{"text":"Say OK"}]}]' \
  --query 'output.message.content[0].text' --output text
```

If this fails, stop here and fix model access. Every script below will fail the same way.

## 5. Install

With `uv` (the path every number in `article.md` was measured on):

```bash
uv venv --python 3.11
VIRTUAL_ENV=.venv uv pip install strands-agents==1.63.0 strands-agents-tools==0.8.11
```

With plain `venv` and `pip`, if you do not use `uv`:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install strands-agents==1.63.0 strands-agents-tools==0.8.11
```

Verify the install before going further:

```bash
.venv/bin/python -c "from importlib.metadata import version; print(version('strands-agents'))"
```

Expected: `1.63.0`. If `pip` cannot resolve `boto3`, the problem is network access to PyPI
and not the package itself; `uv` uses a different resolver and may succeed where `pip` fails.

Pin the versions. The SDK ships a minor release roughly every week, and the numbers in
`article.md` were measured against 1.63.0.

## 6. Step by step

### Step 1: run the defaults and watch them fail

```bash
python src/01_default.py
```

This script prints what the SDK resolved before it calls anything, then fails. Look for these
two lines in the output:

```text
└ Bedrock region: us-east-1
└ Model id: global.anthropic.claude-sonnet-4-6
```

The SDK tells you its own resolved configuration. The docs list `us-west-2` as the default
region, and your machine may resolve something else entirely.

### Step 2: pin the model and the region

```bash
python src/02_pinned.py
```

Expected output:

```text
STOP_REASON : end_turn
TEXT        : The largest ocean on Earth is the Pacific Ocean.
USAGE       : {'inputTokens': 16, 'outputTokens': 11, 'totalTokens': 27}
CYCLE_COUNT : 1
```

One cycle means the model never asked for a tool.

### Step 3: add a tool and force a second cycle

```bash
python src/03_tools.py
```

Expected output (the measured run, which is one of several valid shapes):

```text
STOP_REASON : end_turn
USAGE       : {'inputTokens': 4839, 'outputTokens': 202, 'totalTokens': 5041}
CYCLE_COUNT : 3
TOOL        : calculator calls=2 success=2 error=0
```

You will also see a deprecation warning. It is expected, and it is discussed in step 10.

### Step 4: read the span tree

```bash
python src/04_trace.py
```

The output is verbose OTLP JSON. Filter for the parts that matter:

```bash
grep -oE 'event_loop\.cycle_id[^,]*|parent_cycle_id[^,]*|gen_ai\.tool\.name[^,]*' \
  <(python src/04_trace.py)
```

Each cycle carries the id of the cycle before it, which is how you prove the loop actually
chained rather than ran once and guessed.

### Step 5: watch the loop recurse

```bash
python src/05_recursion.py
```

```text
cycle 1 begins (recursion depth 1)
  cycle 2 begins (recursion depth 2)
  cycle 2 ends
cycle 1 ends
```

The script wraps `strands.event_loop.event_loop.recurse_event_loop` and prints the stack
depth. There is no `while` in the loop: a cycle that ran a tool calls `recurse_event_loop`
(`event_loop.py:1231`), which calls `event_loop_cycle` again one frame down.

### Step 6: read the cycle ids

```bash
python src/06_cycle_ids.py
```

```text
MODEL CALL  cycle=5e8cebb8  parent=-
TOOL RESULT cycle=5e8cebb8  parent=-
MODEL CALL  cycle=6913ddf0  parent=5e8cebb8
```

Two hooks print the keys the loop itself writes into `invocation_state`: the id at
`event_loop.py:230` and the parent id at `event_loop.py:1109`. No tracer involved.

### Step 7: price one tool

```bash
python src/07_tool_schema.py | head -5
```

```text
TOOL_COUNT  : 1
TOOL_NAME   : calculator
SPEC_CHARS  : 5500
```

The docstring becomes the description and the type hints become the schema, and the whole
block travels with every cycle. That is why 27 tokens became 5041.

### Step 8: read the defaults without calling Bedrock

```bash
python src/08_defaults.py
```

```text
BOTO_REGION             : us-east-1
DEFAULT_BEDROCK_REGION  : us-west-2
DEFAULT_BEDROCK_MODEL_ID: global.anthropic.claude-sonnet-4-6
PREFIXED_VARIANT        : us.anthropic.claude-sonnet-4-6
RESOLVED_MODEL_ID       : global.anthropic.claude-sonnet-4-6
CLIENT_REGION           : us-east-1
```

The region fallback is one line at `bedrock.py:323`: your argument, then the boto session,
then `AWS_REGION`, then the constant.

### Step 9: watch the conversation grow

```bash
python src/09_messages.py
```

```text
TURN cycle=94b99f5d  messages=1
     user[text]
TURN cycle=f3dfd557  messages=3
     user[text] | assistant[text+toolUse] | user[toolResult]
FINAL       : user[text] | assistant[text+toolUse] | user[toolResult] | assistant[text]
MESSAGES    : 4
```

Tool results come back as a user-role message (`event_loop.py:1087`), so turn two sees
three messages where turn one saw one. The conversation is the only channel between cycles.

### Step 10: the deprecation warning

`calculator` prints this:

```text
DEPRECATION WARNING: calculator is deprecated. This warning becomes an error log
in v0.9.0. To achieve similar functionality, use the shell tool vended by
strands-agents (from strands.vended_tools import shell).
```

Read the second half carefully. The suggested replacement is `shell`, and the official
warning states that this changes the security boundary, because `calculator` only evaluated
an expression checked against an AST allowlist while `shell` executes arbitrary commands. Do
not swap them in production without reviewing that trade. Article UC02 covers this migration
in full.

## 7. Verify

Assert the four things this use case claims.

```bash
python - <<'PY'
from strands import Agent
from strands.models import BedrockModel
from strands_tools import calculator

model = BedrockModel(model_id="deepseek.v3.2", region_name="us-east-1")

plain = Agent(model=model, callback_handler=None)(
    "In one sentence, what is the largest ocean on Earth?")
assert plain.stop_reason == "end_turn"
assert plain.metrics.cycle_count == 1

tooled = Agent(tools=[calculator], model=model, callback_handler=None)(
    "What is the square root of 1764, plus 8?")
assert tooled.metrics.cycle_count >= 2
assert "calculator" in tooled.metrics.tool_metrics
print("all assertions passed")
PY
```

Note that `cycle_count` is asserted as `>= 2` rather than `== 2`. The model decides how many
turns it takes, so an exact assertion will flake. Measured values were 2 cycles on most runs
and 3 on one.

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ValidationException ... unsupported countries` | the default model is Anthropic and your location cannot invoke it | pin a model you can call, as in step 2 |
| `Could not connect to the endpoint URL` | the region has no Bedrock endpoint you can reach | pass `region_name="us-east-1"` explicitly |
| `ValidationException: Invocation of model ID ... isn't supported` | the model needs an inference profile | use the profiled id, such as `us.deepseek.r1-v1:0` |
| `ModuleNotFoundError: strands_tools` | the tools package is not installed | `pip install strands-agents-tools==0.8.11` |
| `text` comes back `None` but tokens were spent | you used a reasoning model such as DeepSeek-R1, whose output arrives in a reasoning block | use `deepseek.v3.2` for the walkthrough |

## 9. Cost and cleanup

Every script only invokes a model. There is nothing to delete, no stack to tear down and no
storage to clear. The measured runs cost well under one US cent each.

To remove the environment:

```bash
deactivate
rm -rf .venv
```

## 10. Going further

- UC02 covers the tool layer, including the `vended_tools` migration that `calculator` is
  part of.
- UC03 covers the four execution boundaries, which is where the unpredictable cycle count
  from this article gets contained.
- The Strands docs on the agent loop: <https://strandsagents.com/docs/user-guide/sdk/agents/agent-loop/>
