# The Agent That Wouldn't Start

> Verified on 2026-11-01 against `strands-agents` 1.63.0, Python 3.11 and Bedrock in
> `us-east-1`. Every number below came out of a run, and the setup steps live in `README.md`.
> The model is `deepseek.v3.2` running on Amazon Bedrock.

## The problem

You want an agent. You know what an agent is, roughly: a loop. You ask a model something,
the model asks for a tool, you run the tool and hand the result back, and the model answers
again. You have written enough loops to guess this one at a few hundred lines, plus retry
logic, plus something to stop the context from overflowing.

Then you open the Strands Agents README and it claims the whole thing is three lines.

```python
from strands import Agent

agent = Agent()
agent("What is the largest ocean on Earth?")
```

I copied those three lines and ran them. They did not run.

## Why the obvious approach breaks

The failure is not subtle, and it lands before any of my own logic executes. This is the
whole run, printed by the SDK itself.

![The default run fails, and the SDK prints the region and model it resolved](/images/the-loop/S1-default-fails.png)

Three defaults decided this before I wrote a line of my own. The default provider is
`BedrockModel`. The default model is `global.anthropic.claude-sonnet-4-6`. The documented
default region is `us-west-2`. Anthropic models carry a geographic restriction that this
account cannot satisfy, so the call fails before any of my own logic runs.

None of that appears in the three lines. All of it hides inside them, and that gap is the
point of this series. The loop is cheap, but the decisions inside it are not free.

## Architecture

Strands emits an OpenTelemetry span for every layer, so I read the shape off a real run
instead of off a diagram somebody drew.

![The agent loop as the spans describe it: one call, two cycles, each cycle naming its parent](/images/the-loop/F1-agent-loop.png)

The model drives the loop. It decides whether it needs a tool, calls it, reads what came back
and decides whether it is finished. Because the model is the one that knows when it is done,
the loop only keeps offering another turn until the model stops asking. That is what
"model-driven" means in practice. You do not draw the workflow, so the model walks it.

That is also the trade. A framework that makes you draw the graph tells you in advance how
many steps a request takes, because you wrote the steps. A model-driven loop cannot tell you
that, because the number of steps is an output of the model rather than a property of your
code. You trade predictability for a much shorter program. Getting some of it back is what
most of this series is about.

## Walkthrough

The fix is to stop accepting the defaults. First I checked what this account can actually
invoke, because listing a model is not the same as being allowed to call it.

```bash
aws bedrock list-foundation-models --region us-east-1 \
  --query 'modelSummaries[].{id:modelId,provider:providerName}' --output text \
  | grep -i deepseek
```

That returns two ids. `deepseek.v3.2` supports on-demand invocation, so it needs no inference
profile, and that is the one I used.

```text
deepseek.r1-v1:0     DeepSeek
deepseek.v3.2        DeepSeek
```

Amazon Bedrock carries DeepSeek, so I pointed the model id there.

```python
from strands.models import BedrockModel

model = BedrockModel(
    model_id="deepseek.v3.2",
    region_name="us-east-1",
)
```

One string changed, and the same three lines work. That is the part of Strands I would keep
even if I threw the rest away: the model is a parameter, not an architecture, so swapping a
provider is a one-line edit rather than a rewrite. The SDK treats Bedrock, Anthropic, OpenAI
and a long list of OpenAI-compatible endpoints the same way. Bedrock happened to carry the
model I wanted.

```python
agent = Agent(model=model)
result = agent("In one sentence, what is the largest ocean on Earth?")
```

To watch the loop take more than one turn, I gave it a tool and a question that forces the
tool to run.

```python
from strands_tools import calculator

agent = Agent(tools=[calculator], model=model)
result = agent("What is the square root of 1764, plus 8?")
```

That call prints a warning I did not expect, and I will come back to it.

## Verification

The first question answers in one turn, because the model never needs a tool.

![One cycle, 27 tokens, end_turn](/images/the-loop/S2-pinned.png)

The second question reaches for the calculator, and the loop takes more turns.

![A tool forces the loop into three cycles and two calculator calls](/images/the-loop/S3-tools.png)

The span tree confirms the handoff, and each cycle names its parent.

![Every cycle carries the id of the cycle before it](/images/the-loop/S4-trace.png)

The token count is the part worth staring at. The plain question cost 27 tokens and the
calculator question cost more than five thousand, even though the answer barely changed.
Most of the difference is the tool's schema riding along in the prompt on every cycle, so a
single tool can cost more than a hundred words of conversation. That is the first thing I
check now whenever an agent gets expensive, and it is the reason the next article exists.

If you want to assert any of this rather than read it, the metrics are plain attributes.

```python
assert result.stop_reason == "end_turn"
assert result.metrics.cycle_count >= 2
assert "calculator" in result.metrics.tool_metrics
print(result.metrics.accumulated_usage)
```

Note that the cycle count is asserted as `>= 2` rather than `== 2`. The number of turns is an
output of the model, so an exact assertion will flake.

## What surprised me

Four things, and each one cost me time to find.

The default region is not a mystery you have to solve. The SDK prints what it resolved, in
the same output as the failure. Look at the last two lines of the first figure again:

```text
| Bedrock region: us-east-1
| Model id: global.anthropic.claude-sonnet-4-6
```

The docs say `us-west-2` and my machine resolved `us-east-1` through the boto session, so the
documented value was the one thing I should not have trusted. Read the printed line before
you read the docs.

The deprecation warning has teeth. The official replacement for `calculator` is `shell`, and
the warning says so plainly:

```text
This does change the security boundary: calculator only ever evaluated an
expression checked against an AST allowlist, while shell executes arbitrary
commands, so review it against your threat model before switching.
```

A tool that could only do arithmetic is being replaced by one that runs anything. That is
not a like-for-like swap, and the hello-world example walks straight into it. It also stops
being a warning soon, because the message states that it becomes an import error in v0.9.0.

You can see the trade in the two imports side by side.

```python
from strands_tools import calculator            # AST allowlist, safe, deprecated
from strands.vended_tools import shell          # arbitrary commands, supported
```

I stayed on `calculator` for this walkthrough on purpose. Switching to `shell` to silence a
warning is the kind of change that passes review and quietly widens what the agent may do.

The model choice moves the numbers more than the code does. Same agent, same question, one
string changed.

![Same code, one string changed: the token counts nearly match and the latency does not](/images/the-loop/S5-model-swap.png)

The token counts land within four percent of each other and the latency differs by more than
six times. Nothing in my code explains that gap.

The loop is not deterministic. I asked the calculator question four times on the same SDK
version and got two cycles twice, three cycles once and two cycles again, with the token
count ranging from 3234 to 5041. The model also called the calculator twice on one run and
once on the others. Nothing in my code changed between those runs, so any test that asserts
an exact cycle count will flake.

## When not to use this

Strands is a library that runs inside your process. It is not a hosted control plane and it
does not want to be one, so it ships no scheduler, no database and no console of its own. If
what you need is a managed runtime, a gateway, identity brokering, or a catalog of agents
shared across an organization, that is the layer above this one. It is where a service like
Bedrock AgentCore sits. Reach for the loop when you want to own the loop.

## Try it yourself

```bash
git clone https://github.com/pinxiong/strands-in-action.git
cd strands-in-action/usecases/01-the-loop
uv venv --python 3.11
VIRTUAL_ENV=.venv uv pip install strands-agents==1.63.0 strands-agents-tools==0.8.11
```

Confirm the pinned version landed before you trust any output.

```bash
.venv/bin/python -c "from importlib.metadata import version; print(version('strands-agents'))"
```

Then run the same four scripts that produced every number above.

```bash
python src/01_default.py     # fails on purpose: the default model is geo-gated
python src/02_pinned.py      # one cycle, one answer
python src/03_tools.py       # more cycles, one tool
python src/04_trace.py       # the span tree
```

And if you want the span tree without the surrounding OTLP noise:

```bash
python src/04_trace.py | grep -oE 'event_loop\.cycle_id[^,]*|parent_cycle_id[^,]*'
```

The first script fails by design, which is the fastest way to see the defaults for yourself.

Takeaways. The three lines are real, and they carry three defaults you did not choose. Read
the region the SDK prints before you trust the region in the docs. The model drives the loop,
so the model decides how many turns you pay for. And a deprecation warning in a hello-world
example is still worth reading, because the replacement may not be the same tool.
