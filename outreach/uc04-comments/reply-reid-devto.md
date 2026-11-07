You are right about where the tokens go, and there is one SDK detail that makes the fix more work than it sounds. Since your comment I have written the mechanism into the article itself, as the section "State does not inject itself" — the hook and the run below are in it.

Your read matches what the article measured from the other side. The session wrote fourteen messages to disk while the window held six, and at turn seven the codename was gone from the prompt. The model did not say it did not know. It answered with a privacy refusal instead: "Sorry, I can't respond in a way that might provide private and sensitive information." That is the pruning cost you describe, surfacing as a policy answer.

The correction: in strands-agents 1.63.0, `agent.state` does not reach the model by itself. `FileSessionManager` writes it through `SessionAgent.from_agent` (`state=agent.state.get()`, `types/session.py:145`, inside the method defined at `:126`) and reloads it at `session/repository_session_manager.py:262` (`agent.state = AgentState(session_agent.state)`); `SnapshotSessionManager` goes through `take_snapshot`/`load_snapshot` instead (`agent/agent.py:2262`, `:2304`). Either way, nothing in the prompt path reads it. `system_prompt` is typed `str | list[SystemContentBlock] | None` (`agent/agent.py:243`), not a callable, so there is no built-in per-invocation injection either. The manifest is yours to build.

The place I used is a `BeforeInvocationEvent` hook (`hooks/events.py:39`) plus the `system_prompt` setter (`agent/agent.py:812`):

```python
BASE_PROMPT = "You are a concise assistant."

def inject_manifest(event: BeforeInvocationEvent) -> None:
    manifest = json.dumps(agent.state.get(), sort_keys=True)
    agent.system_prompt = f"{BASE_PROMPT}\n\n<manifest>\n{manifest}\n</manifest>"

agent.add_hook(inject_manifest, BeforeInvocationEvent)
```

I ran your prescription against the article's setup: `window_size=6`, one session, seven turns, the codename planted in both the message and `agent.state`. At turn seven the message list held six messages, fourteen were on disk, and ORION was absent from `agent.messages`:

```
ORION_IN_MESSAGES_BEFORE_ASK: False
ROLES_BEFORE_ASK: ['user', 'assistant', 'user', 'assistant', 'user', 'assistant']
TURN 7 ask     | msgs= 6 stored=14 | ORION
ORION_IN_SYSTEM_PROMPT: True
```

Same window, same seven turns, opposite outcome from the run in the article: the model answered "ORION". I re-ran this probe today before replying and got the same four lines, so it is not a one-off. That is the gap between storing an invariant and surfacing it, and it is the part of your design that has to be code rather than architecture.

Two claims I would state more narrowly. On the summarizer losing precision on specific parameters: in our seven-turn run it kept the codename — the summary it injected opens with a "## Conversation Summary" header and contains the line "The user, identified by the codename ORION, requested a summary of the conversation". The cost you describe is real though, and it shows up in the window arithmetic: seven turns is fourteen messages, the window held nine at the end, and the oldest of those nine is the summary itself, so six messages were dropped and one summary took their place. Fidelity depends on what the summarizer chose to keep, and seven turns is too short to show degradation; I would expect it with longer tails and more numbers, not on turn seven.

On TTFT I have no measurement to offer, so the honest version is that input grows with the window, which is arithmetic. On my side the fix added no messages — but it does add the serialized state to the system prompt on every call, which is tokens the article never measured, so I would not call it free either.

Net: I agree with the architecture. In this SDK the injection is yours to write, for state that changes it has to be refreshed on every invocation rather than written once at construction, and it gives the model a channel to the invariant the window dropped.
