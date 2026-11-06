Fernando, thank you, and your question is the one that decides whether the boundary means anything.

I ran your exercise on the remote endpoint (server 0.4.1) this afternoon. The short answer: the boundary holds on your side and leaks on the input side, before the model writes a single line of prose.

`requirements_check` behaved exactly right. `requirements: []`, `constraints: []`, and the missing SLO, RTO, RPO and budget came back as seven open questions instead of invented values. Then `capacity_plan` asked for `durationMs` and `payloadKB`, and the brief contains neither. The schema rejected the call, which is correct. But the exercise asks for a capacity discussion, so to continue I supplied 250 ms and 4 KB. The response placed those next to the 500 rps I actually had, inside one `assumptions` object, and returned 163 planned concurrency on top of them.

That is the part I did not expect. Your server never invented a number. I did, and the payload had no way to record where each value came from, so the two kinds of number arrived at the reader in the same shape.

I wrote the full report with the calls, the exact responses and three suggested fixes in your issue #19. The one I would fix first is making `durationMs` and `payloadKB` optional, so the tool can answer "this cannot be sized yet" the way `requirements_check` already answers "these requirements are still open".
