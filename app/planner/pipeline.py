"""
The single orchestration function that runs the entire pipeline for a
goal. This is what both the FastAPI /plan endpoint and the FastMCP tool
call — keeping the actual logic in one place so they can't drift apart.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.planner.architecture import generate_architecture
from app.planner.decompose import decompose_goal
from app.planner.explain import explain_all
from app.planner.match import match_capabilities
from app.planner.rank import rank_all
from app.planner.workflow import build_workflow


def run_plan(goal: str) -> dict[str, Any]:
    """
    Runs the full pipeline and returns a dict matching app.models.PlanResponse.

    Stage ordering and concurrency:
      1. decompose_goal               — must be first; everything else depends on it
      2. match_capabilities           — needs capabilities list
      3. rank_all                     — needs match results
      4. explain_all ∥ build_workflow — both depend only on `ranked`;
                                        run concurrently to halve latency here
      5. generate_architecture        — depends on workflow; runs after step 4
    """
    capabilities = decompose_goal(goal)

    matches = match_capabilities(capabilities)
    ranked = rank_all(matches)

    # explain_all and build_workflow are independent — run them in parallel.
    # explain_all itself also parallelises its per-capability LLM calls
    # internally, so the combined step takes ~max(explain, workflow) not their sum.
    with ThreadPoolExecutor(max_workers=2) as executor:
        explain_future = executor.submit(explain_all, ranked)
        workflow_future = executor.submit(build_workflow, goal, ranked)
        explanations = explain_future.result()
        workflow = workflow_future.result()

    architecture = generate_architecture(goal, workflow)

    unmatched_capabilities = [cap for cap, candidates in ranked.items() if not candidates]

    recommendations: dict[str, list[dict[str, Any]]] = {}
    for capability, candidates in ranked.items():
        if not candidates:
            continue
        cap_explanations = explanations.get(capability, {})
        enriched = []
        for candidate in candidates:
            enriched.append({
                **candidate,
                "explanation": cap_explanations.get(candidate["repo_full_name"]),
            })
        recommendations[capability] = enriched

    return {
        "goal": goal,
        "capabilities": capabilities,
        "unmatched_capabilities": unmatched_capabilities,
        "recommendations": recommendations,
        "workflow": workflow,
        "architecture": architecture,
    }


if __name__ == "__main__":
    import json

    result = run_plan("Build an AI accountant that reads invoices and files taxes")
    print(json.dumps(result, indent=2, default=str))