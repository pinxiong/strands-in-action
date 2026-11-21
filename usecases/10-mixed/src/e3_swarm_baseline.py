"""E3 — pure Swarm: three nodes drive themselves with handoff_to_agent.

Records the handoff order (node_history), the final keys in SharedContext,
and the real per-node token usage.

    ../../.venv/bin/python src/e3_swarm_baseline.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from strands.multiagent import Swarm

from common import (
    LEDGER, NODE_TURNS, SWARM_INSTRUCTIONS, TASK, TOOLS,
    NodeRecorder, base, emit, first_input, node_agents, reset, usage_of,
)

ORDER = ["researcher", "calculator", "writer"]


def run() -> dict:
    reset()
    agents, counters = node_agents(SWARM_INSTRUCTIONS, TOOLS)
    swarm = Swarm(
        nodes=[agents[name] for name in ORDER],
        entry_point=agents["researcher"],
        max_handoffs=10,
        max_iterations=10,
        hooks=[NodeRecorder()],
    )

    started = time.time()
    result = swarm(TASK)
    wall = time.time() - started

    # SharedContext is swarm-private; enumerate its final keys verbatim.
    shared_context = json.loads(json.dumps(swarm.shared_context.context, default=str))
    shared_context_keys = {node_id: sorted(keys) for node_id, keys in shared_context.items()}

    per_node = {}
    for name in ORDER:
        nr = result.results.get(name)
        per_node[name] = {
            "model_calls": counters[name].calls,
            **(usage_of(nr) if nr else {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0}),
            "status": nr.status.value if nr else "never ran",
            "wall_ms": nr.execution_time if nr else 0,
        }

    u = result.accumulated_usage
    record = {
        **base("E3 pure Swarm (three-node handoff)"),
        "status": result.status.value,
        "execution_count": result.execution_count,
        "handoff_order_node_history": [str(n) for n in result.node_history],
        "shared_context_final": shared_context,
        "shared_context_final_keys": shared_context_keys,
        "wall_clock_s": round(wall, 3),
        "execution_time_ms": result.execution_time,
        "tokens_total": {
            "inputTokens": u.get("inputTokens", 0),
            "outputTokens": u.get("outputTokens", 0),
            "totalTokens": u.get("totalTokens", 0),
        },
        "model_calls_total": sum(c.calls for c in counters.values()),
        "per_node": per_node,
        "node_turns": [
            {"node": t["node"], "duration_s": round(t.get("stop", t["start"]) - t["start"], 3)}
            for t in NODE_TURNS
        ],
        "first_inputs": {name: first_input(a) for name, a in agents.items()},
        "results_text": {name: str(nr)[:320] for name, nr in (result.results or {}).items()},
        "ledger": list(LEDGER),
    }
    emit("e3-swarm-baseline", record)
    return record


if __name__ == "__main__":
    run()
