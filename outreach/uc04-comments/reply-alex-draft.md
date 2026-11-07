You are right that the two failures need different tests, and running the one you describe changed what I would write down.

I built it as a decision contract rather than a recall check: the fact is a deploy policy, the answer is a decision, and the grader reads the decision. The policy is intentionally arbitrary so the model cannot guess it — build 1.4.2 is exempt from the freeze and must be approved without a sign-off code. Window of six messages, one session, plant at turn 1, ask N turns later.

Same process, no other change:

```
gap 0  -> 2 msgs visible, approves   retrieval ok   behaviour ok
gap 2  -> 6 msgs visible, approves   retrieval ok   behaviour ok
gap 3  -> 6 msgs visible, rejects    retrieval FAIL behaviour FAIL
gap 8  -> 6 msgs visible, rejects    retrieval FAIL behaviour FAIL
```

So the split you asked for is exactly one turn wide: at gap 2 the plant is still in the window and the decision is right; one turn later it is gone and the agent confidently does the opposite. The restart case splits the same way: plant, eight fillers, exit, new process restores the session — 18 messages on disk, 6 in the window, fact gone, wrong decision. At gap 0 the same restart passes, which is how a restart test can stay green over a real defect.

Two things the exercise taught me about the test itself:

1. Retrieval alone would have signed off a broken agent. My first manifest stored only the code (`{"signoff_code": "KESTREL-9"}`) instead of the invariant. At gap 8 the prompt did contain the code, a "does the fact reappear" assertion passed, and the model still rejected the exempt build — it saw the code and applied the rule the code belongs to. Storing the whole policy text instead flipped the answer to approve. Same channel, opposite behaviour.

2. Behaviour alone would have passed for the wrong reason. With the ordinary rule (no code, so reject), at gap 3 the fact was gone and the answer was still "rejected" — because my question mentions a missing sign-off code, so the prior does the work. The exemption policy is what makes the check discriminating: there, guessing gives the wrong answer.

Script and raw output: https://github.com/pinxiong/strands-in-action/tree/master/outreach/uc04-comments. The runs differ only in `--gap`, `--inject` and `--state`, and every row prints `FACT_IN_MESSAGES` / `FACT_IN_PROMPT` next to `BEHAVIOR_PASS`, so a green retrieval cannot hide a red decision.
