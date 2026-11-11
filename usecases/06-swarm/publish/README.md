# UC06 · Orchestrating Agents: Nobody Decides Who Goes Next

状态：**已发布**（2026-11-11）

| 渠道 | 线上地址 |
|---|---|
| 主站 | https://xiongpin.dev/posts/orchestrating-swarm/ |
| AWS Builder Center | https://builder.aws.com/content/3Lxn0RS1k0tiClcigN1xz5c0hH9 |
| Dev.to | https://dev.to/aws-builders/orchestrating-agents-nobody-decides-who-goes-next-2cg4 |
| Medium | <MEDIUM_URL> — 待手动 Import（人工物料已齐：Medium 手册 + Slack 文案 + 16:9 封面） |

> Verified on 2026-11-11 against `strands-agents` 1.63.0, Python 3.11 and Bedrock in
> `us-east-1`. The model is `amazon.nova-pro-v1:0`.
> Every number in the article came out of a run; raw output lives in `evidence/`.

A swarm has no scheduler, no route table and no orchestrator queue. Routing is a model's
tool call (`handoff_to_agent`), termination is silence, and `completed` means nobody asked
for help. This case runs the mechanism until it breaks: eight-word vs six-word deliverables
from the same task, a handoff that dies with its node, a broken tool that does not stop the
swarm, and two limit knobs that read the same counter.

## What the experiments show

| Script | Question | Finding |
|---|---|---|
| `src/swarm_trace.py --mode happy` | What does a healthy handoff chain look like? | `researcher -> calculator -> writer`, 3 node turns, 8857 tokens, eight-word deliverable; a second run with no changes: 8605 tokens, six words |
| `src/swarm_trace.py --mode silent` | What if the entry node says nothing? | `completed` with `execution_count: 1`, writer never ran, 718 tokens — status measures liveness, not the task |
| `src/swarm_limits.py` | Do `max_handoffs` and `max_iterations` differ? | Both read `len(node_history)`; ping-pong pair stops at turn 3 either way, only the reason string differs; hitting a cap marks the swarm `failed` |
| `src/swarm_failure.py --mode toolerror` | Does a broken tool stop the swarm? | No: the error goes back to the model as a tool result, handoff survives, writer runs and calls `save_draft` 11 times |
| `src/swarm_failure.py --mode timeout` | What happens to a handoff when its node times out? | The handoff is rolled back (`_rollback_uncommitted_turn`), the successor never runs, and the failure report says zero tokens |
| `src/swarm_failure.py --mode cancel` | Where can a human intervene? | `BeforeNodeCallEvent` cancels one node before it starts; nothing pre-empts a node already spending tokens |
| `src/swarm_failure.py --mode session` | Can a node keep its own session? | No: `ValueError: Session persistence is not supported for Swarm agents yet.` |

## Reproduce

```bash
git clone https://github.com/pinxiong/strands-in-action.git
cd strands-in-action/usecases/06-swarm
uv venv --python 3.11
VIRTUAL_ENV=.venv uv pip install strands-agents==1.63.0
python src/swarm_trace.py --mode happy
```

All seven modes are listed at the end of the article (`Try it yourself`). The happy path
needs Bedrock access to `amazon.nova-pro-v1:0`; the session mode fails at construction
with no model call. Run happy twice and diff the two `save_draft` entries.

## Scope

Single process, three agents, one model, a task that finishes in fifteen seconds. The
numbers describe runtime behaviour, not output quality. The repetitive-handoff detector
(off by default) and resumption from a session are not covered.
