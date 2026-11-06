# UC04 · Sessions, State & Memory

> Verified on 2026-11-06 against `strands-agents` 1.63.0, Python 3.11 and Bedrock in
> `us-east-1`. The model is `amazon.nova-pro-v1:0` (switch with `MODEL_ID=deepseek.v3.2`).
> Every number below came out of a run; raw output lives in `evidence/`.

One agent, three kinds of memory: a message list on disk, a JSON state store, and the window
the model can actually see. Each one can succeed while another fails.

## What the experiments show

| Script | Question | Finding |
|---|---|---|
| `src/session_restart.py` | Does a session survive a process restart? | Second process, same session id, answers "Your name is Pin and your favorite number is 42"; 4 files after run one, 6 after run two, one file per message |
| `src/agent_state.py` | What is `agent.state` and what does it refuse? | `visits=1` and a nested dict survive a restart; `object()` raises `ValueError: Value is not JSON serializable` at write time |
| `src/sliding_window.py` | What does the model see after the window trims? | `window_size=6`: stored messages climb 2→14, `agent.messages` locks at 6, the codename disappears and the model answers with a privacy refusal |
| `src/summarizing_window.py` | Does summarizing keep the fact? | At `COMPRESSION_THRESHOLD=0.001` nothing happens: 14 messages, no summary. At the default 0.00005 proactive compression fires, the count settles at 9, the oldest message becomes `## Conversation Summary`, and the codename survives |
| `src/snapshot_session.py` | How does the newer manager differ on disk? | Same restart recall from a single `snapshot_latest.json` that grows 878→1774 bytes instead of a file per message |

## Reproduce

From the repository root, create the environment the way the top-level `README.md` describes
(`uv venv --python 3.11`, then `VIRTUAL_ENV=.venv uv pip install strands-agents==1.63.0`),
activate it and run the scripts from this directory. The restart probes take `first` and
`second` as arguments and must be separate processes.

```bash
cd usecases/04-sessions-state-memory
python src/session_restart.py first
python src/session_restart.py second
python src/agent_state.py first
python src/agent_state.py second
python src/sliding_window.py
python src/summarizing_window.py
COMPRESSION_THRESHOLD=0.001 python src/summarizing_window.py
python src/snapshot_session.py first
python src/snapshot_session.py second
```

Throwaway state lands in `src/sessions_tmp/` and `src/snapshots_tmp/`; delete both to start clean.
The two summarizing runs share `session_id="summary-demo"`, so delete
`src/sessions_tmp/session_summary-demo` between them.

## Source anchors (strands-agents 1.63.0)

- `session/file_session_manager.py:31-45` — on-disk layout: `session.json`, `agent.json`, `messages/message_<id>.json`
- `session/file_session_manager.py:202` — `agent.json` write path, the file that holds state and manager bookkeeping
- `agent/conversation_manager/sliding_window_conversation_manager.py:150` — `apply_management`: one `len(messages) <= window_size` check, in-memory only
- `agent/conversation_manager/conversation_manager.py:125-145` — proactive compression: `projected_input_tokens` against `estimate_utilization`, threshold as a ratio of the context window
- `event_loop/event_loop.py:629-639` — where `projected_input_tokens` is estimated and attached to `BeforeModelCallEvent`
- `agent/conversation_manager/summarizing_conversation_manager.py:48-75` — constructor and docstring: summarization is triggered by context pressure, not by a message count
- `session/snapshot_session_manager.py:1-17` — snapshot design: one atomic blob, `snapshot_latest` overwritten, "recommended path for new agents"
- `storage/local_file_storage.py` / `storage/s3_storage.py` / `storage/in_memory_storage.py` — the three storage backends a snapshot manager can write through
- `types/json_dict.py` — `JSONSerializableDict`, the type behind `agent.state`
