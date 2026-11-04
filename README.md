# Strands in Action

Eight independent experiments on one SDK. Every article is a use case, every use case runs,
and every number in every article came out of a real run.

Strands Agents is an open-source SDK from AWS for building AI agents. It is a library, not a
platform: it runs inside your own process, with no control plane to stand up first. This
series is about the layer you write yourself.

> Verified against `strands-agents` 1.63.0 on 2026-11-01. See [Version policy](#version-policy).

---

## Two series, one dividing line

This repository is the companion to [`bedrock-agentcore-in-action`](https://github.com/pinxiong/bedrock-agentcore-in-action).
The split is deliberate:

| | bedrock-agentcore-in-action | strands-in-action (here) |
|---|---|---|
| Subject | a managed service | an open-source SDK |
| Question | what the cloud carries for you | what you write and own yourself |
| Unit of analysis | 14 AgentCore capabilities | 8 use cases on one loop |
| Runs where | on AWS | anywhere, including your laptop |

Strands agents deploy to AgentCore Runtime, and AgentCore accepts almost any framework. They
are not competing layers, so the two series cross-link instead of overlapping: the AgentCore
articles point here for the loop and the tool contract, and the Strands articles point back
for managed memory and runtime.

## The eight articles

Three acts. One article takes the principle apart, four build capability on top of it and
three cover what it takes to trust the result in production.

| Act | # | Article | D | Capabilities folded in | Status |
|:--:|:--:|---|:--:|---|:--:|
| **Principle** | 01 | [How the Strands Agent Loop Actually Works](usecases/01-the-loop/article.md) | D1 | agent loop, model providers, hidden defaults, trace, streaming | article + code + evidence |
| **Capability** | 02 | The Tools That Got Replaced | D2 | `@tool`, JSON schema, structured output, `vended_tools` migration, MCP | planned |
| | 03 | Stopping an Agent That Won't Stop | D2 | limits, token budget, tool quotas, cancel, hooks | planned |
| | 04 | What Your Agent Remembers After a Restart | D3 | sessions, agent state, conversation manager, long-term memory | planned |
| | 05 | Four Ways to Split One Brain | D4 | Swarm, Graph, Workflow, A2A | planned |
| **Production** | 06 | When the Agent Asks First | D4 | guardrails, PII, interrupt and resume, human in the loop | planned |
| | 07 | Did It Get Worse? | D4 | trace deep dive, 13+ evaluators, LLM-as-judge | planned |
| | 08 | The Same Agent, Six Addresses | D5 | AgentCore, Lambda, Fargate, App Runner, EKS, EC2 | planned |

Article 01 is the foundation. It takes the loop apart in the source so the other seven can
start from a use case instead of from first principles. Each later article assumes specific
sections of 01 and says which ones at the top.

Capabilities are folded into use cases rather than mapped one-to-one. `structured_output` is
implemented as a schema-to-tool conversion, so it belongs with the tools article. `hooks` are
how limits get enforced, so they belong with the limits article. PII is a kind of guardrail.

### Difficulty ladder

| Level | Meaning | Approx. time |
|:--:|---|---|
| D1 | one or two new capabilities | under 30 minutes |
| D2 | one or two, with a real failure to debug | about an hour |
| D3 | two or three, state involved | about two hours |
| D4 | three to five, orchestration or evaluation | three to four hours |
| D5 | five or more, deployment | about four hours |

The sequence runs 1, 2, 2, 3, 4, 4, 4, 5 and never decreases.

## Quick start

Every use case is self-contained. Start anywhere, though the first one explains the defaults
that the rest assume you know.

```bash
git clone https://github.com/pinxiong/strands-in-action
cd strands-in-action/usecases/01-the-loop
uv venv --python 3.11
VIRTUAL_ENV=.venv uv pip install strands-agents==1.63.0 strands-agents-tools==0.8.11
python src/02_pinned.py
```

The first script fails on purpose:

```bash
python src/01_default.py
```

You need AWS credentials with Bedrock access and a model your account can invoke. The
walkthrough uses `deepseek.v3.2` on Amazon Bedrock in `us-east-1`.

## Repository layout

```
strands-in-action/
├── README.md            this file
├── PLAN.md              series plan, coverage matrix, risk register
├── LICENSE              Apache 2.0
├── docs/
│   └── 00-facts-baseline.md    cited facts for all eight articles
└── usecases/
    └── NN-slug/
        ├── article.md   the narrative
        ├── README.md    the commands, step by step
        ├── src/         numbered scripts
        └── evidence/    captured output, one file per script
```

`article.md` is the story. `README.md` is what you copy and paste. They are deliberately
separate, and neither repeats the other.

## Version policy

Strands ships a minor release roughly every week. Between 2026-10-12 and 2026-10-30 the SDK
went 1.60.0 → 1.63.0, five releases in eighteen days.

That makes staleness the main risk of a series like this one, so:

- every article states the version and date it was verified against
- every use case pins its dependencies in its own `README.md`
- this section is the version ledger, refreshed as articles are published

| Article | Verified | `strands-agents` | `strands-agents-tools` |
|---|:--:|:--:|:--:|
| 01 | 2026-11-01 | 1.63.0 | 0.8.11 |

Latest on PyPI as of 2026-11-01: `strands-agents` 1.63.0, `strands-agents-tools` 0.8.11,
`strands-agents-evals` 1.8.0.

## Conventions

- **Nothing unverified gets published.** Numbers come from runs, and runs are saved under
  `evidence/`.
- Length follows the content. Articles land around 1000 to 1300 words of prose and run
  longer when a mechanism needs the room, always dense with short code blocks and no tables.
- Every article ends with takeaways and never with a teaser for the next one.
- Account identifiers are redacted to `123456789012` in everything that gets committed.

## License

Apache 2.0. See [LICENSE](LICENSE).
