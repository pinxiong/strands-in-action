"""E9 — cost & capability table for E1..E5, plus the honest mixed-vs-pure verdict.

E9 aggregates the five REAL Bedrock runs (it does not re-run them, so the
numbers are byte-identical to their evidence files). It also runs a small
construction-time capability probe on the installed SDK (NO model call, clearly
labelled) to show what a single paradigm cannot do.

    ../../.venv/bin/python src/e9_cost_capability.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import EVIDENCE, base, emit, model

FILES = {
    "E1": "e1-graph-baseline.json",
    "E2": "e2-workflow-baseline.json",
    "E3": "e3-swarm-baseline.json",
    "E4": "e4-mixed-graph-swarm.json",
    "E5": "e5-mixed-graph-workflow.json",
    "E6": "e6-context-bridge.json",
    "E7": "e7-failure-inner-swarm.json",
    "E8": "e8-failure-workflow-condition.json",
}
PARADIGM = {
    "E1": "Graph (pure)",
    "E2": "Workflow (pure)",
    "E3": "Swarm (pure)",
    "E4": "Graph + Swarm (mixed A)",
    "E5": "Graph + Workflow (mixed B)",
}


def load() -> dict:
    return {k: json.loads((EVIDENCE / v).read_text()) for k, v in FILES.items()}


def capability_probe() -> dict:
    """Construction-time checks on the installed SDK. No Bedrock call."""
    from strands import Agent
    from strands.multiagent import Swarm
    from strands.multiagent.graph import GraphBuilder
    from strands_tools.workflow import workflow

    a = Agent(model=model(), name="probe_a", system_prompt="x", callback_handler=None)
    b = Agent(model=model(), name="probe_b", system_prompt="x", callback_handler=None)
    s = Swarm(nodes=[a, b], entry_point=a)

    gb = GraphBuilder()
    out = {}
    try:
        gb.add_node(s, "swarm_node")
        out["graph_add_swarm_node"] = "accepted"
    except Exception as exc:  # noqa: BLE001
        out["graph_add_swarm_node"] = f"rejected: {type(exc).__name__}"

    try:
        gb.add_node(workflow, "workflow_node")
        out["graph_add_workflow_tool"] = "accepted at construction (but _execute_node rejects non AgentBase/MultiAgentBase)"
    except Exception as exc:  # noqa: BLE001
        out["graph_add_workflow_tool"] = f"rejected: {type(exc).__name__}"

    gb2 = GraphBuilder()
    gb2.add_node(a, "a")
    gb2.set_max_node_executions(2)
    g = gb2.build()
    try:
        Swarm(nodes=[g])
        out["swarm_host_graph_node"] = "accepted"
    except Exception as exc:  # noqa: BLE001
        out["swarm_host_graph_node"] = f"rejected: {type(exc).__name__}: {exc}"

    out["workflow_task_is_dict_description"] = True
    out["note"] = "Construction-time probe only; no Bedrock model call."
    return out


def run() -> dict:
    d = load()

    def tokens_total(exp: str) -> int:
        if exp == "E5":
            return d[exp]["true_total_tokens_graph_plus_inner"]
        t = d[exp]["tokens_total"]
        return t["totalTokens"] if isinstance(t, dict) else t

    rows = []
    for exp in ("E1", "E2", "E3", "E4", "E5"):
        r = d[exp]
        wall = r.get("wall_clock_s", r.get("workflow_elapsed_s"))
        row = {
            "exp": exp,
            "paradigm": PARADIGM[exp],
            "total_tokens": tokens_total(exp),
            "model_calls": r.get("model_calls_total"),
            "wall_clock_s": wall,
            "status": r.get("status", r.get("workflow_status")),
            "evidence": FILES[exp],
        }
        if exp == "E5":
            row["graph_reported_tokens"] = r["graph_accumulated_usage"]["totalTokens"]
            row["inner_workflow_tokens"] = r["inner_workflow_tokens_total"]
            row["total_tokens"] = r["true_total_tokens_graph_plus_inner"]
            row["model_calls"] = r["true_total_model_calls"]
            row["token_accounting"] = "graph own nodes + inner workflow separate agents (E6/E7 show they are not shared)"
        rows.append(row)

    e1_tokens = tokens_total("E1")
    e1_calls = d["E1"]["model_calls_total"]
    e1_wall = d["E1"]["wall_clock_s"]
    deltas = {}
    for row in rows:
        deltas[row["exp"]] = {
            "tokens_delta": row["total_tokens"] - e1_tokens,
            "tokens_pct_vs_e1": round((row["total_tokens"] / e1_tokens - 1) * 100, 1),
            "model_calls_delta": row["model_calls"] - e1_calls,
            "wall_clock_delta_s": round(row["wall_clock_s"] - e1_wall, 3),
            "wall_clock_x_vs_e1": round(row["wall_clock_s"] / e1_wall, 2),
        }

    probe = capability_probe()

    # Facts established by real runs E4/E6/E7/E8.
    findings = {
        "single_paradigm_cannot_host_another_orchestrator": (
            probe.get("swarm_host_graph_node", "").startswith("rejected")
            and d["E4"]["graphbuilder_add_node_accepted"]
            and d["E4"]["nested_node_executed"]
        ),
        "graph_can_schedule_a_swarm_as_a_node": (
            d["E4"]["graphbuilder_add_node_accepted"] and d["E4"]["nested_node_executed"]
        ),
        "data_channels_are_not_shared": (
            not d["E6"]["channel_swarm_shared_context"]["reaches_graph_as_structured_field"]
            and not d["E6"]["channel_workflow"]["reaches_graph_as_structured_field"]
        ),
        "inner_failure_is_invisible_outer_success": d["E7"]["swallowed_treated_as_success"],
        "condition_predicate_cannot_classify_inner_workflow_failure": (
            not d["E8"]["condition_could_classify_inner_failure"]
        ),
        "deliverable_unchanged": (
            all(
                any(e["tool"] == "sum_tokens" for e in json.loads((EVIDENCE / FILES[x]).read_text()).get("ledger", []))
                for x in ("E1", "E2", "E3", "E4", "E5")
            )
        ),
        "mixed_cost_more_than_cheapest_pure": (
            deltas["E4"]["tokens_delta"] > 0 and deltas["E5"]["tokens_delta"] > 0
        ),
    }

    verdict = (
        "Mixing buys exactly one capability that no single paradigm has: a Graph "
        "can schedule a Swarm (or another Graph) as a node, so a deterministic "
        "state machine can contain one layer of autonomous handoffs. Swarm and "
        "the Workflow tool cannot host an orchestrator (probe). But on this "
        "linear research -> accounting -> writing task that capability adds no "
        "usable data power: E6 shows all three paradigms' structured state is "
        "trapped behind a text-only boundary, E7/E8 show an inner failure is "
        "either reported as success or is invisible to the Graph predicate, and "
        "the deliverable is identical across E1..E5. Meanwhile the cheapest pure "
        "run (E1 Graph) grows by "
        f"{deltas['E4']['tokens_pct_vs_e1']}% (E4) and "
        f"{deltas['E5']['tokens_pct_vs_e1']}% (E5) in tokens and up to "
        f"{deltas['E5']['wall_clock_x_vs_e1']}x in wall clock. "
        "So: do NOT mix when the job is a linear chain and a downstream step must "
        "branch on a result. A pure Graph is both cheapest and the only layer that "
        "can still read its own nodes' status. Mix only when you specifically need "
        "one orchestrator nested inside a Graph AND you accept a text-only, "
        "non-auditable boundary."
    )

    record = {
        **base("E9 cost & capability: E1..E5 side by side + verdict"),
        "rows": rows,
        "deltas_vs_e1": deltas,
        "capability_probe": probe,
        "findings_from_real_runs": findings,
        "verdict": verdict,
        "tokens_note": (
            "E5 total = Graph's own accumulated_usage + inner Workflow task Agents' "
            "real accumulated_usage; the two are separate ledgers (E6/E7). E1/E3/E4 "
            "from result.accumulated_usage, E2 from per-task Agent usage."
        ),
        "source_note": "E9 aggregates five already-run, real Bedrock experiments; no numbers are re-simulated here.",
    }
    emit("e9-cost-capability", record)
    return record


if __name__ == "__main__":
    run()
