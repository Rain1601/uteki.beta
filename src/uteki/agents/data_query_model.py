"""Existing metered model adapters used as a single-decision planner."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3

from agents import Agent, ModelSettings, Runner, RunConfig

from uteki.domain.research_data.agent_query import PlannerDecision
from .data_query_agent import PLANNER_PROMPT


def check_prior_budgets(paths, *, acknowledged_unknowns=()):
    """Read-only preflight: a new output folder cannot hide older unknown costs."""
    reports = []
    for path in paths:
        path = Path(path).resolve()
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
            rows = db.execute("SELECT id, reserved, state FROM reservations WHERE state != 'settled'").fetchall()
        reports.append({"path": str(path), "unresolved": [{"reservation_id": r[0], "reserved_usd": r[1], "state": r[2]} for r in rows]})
    actual = {(r["path"], u["reservation_id"], u["reserved_usd"], u["state"])
              for r in reports for u in r["unresolved"]}
    allowed = {(str(Path(a["path"]).resolve()), a["reservation_id"], a["reserved_usd"], "unknown")
               for a in acknowledged_unknowns}
    status = "ready" if not actual else "ready_with_acknowledged_unknown_cost" if actual == allowed else "blocked"
    return {"status": status, "prior_budgets": reports,
            "note": "Acknowledgment does not settle or reclassify unknown costs."}


class SdkQueryPlanner:
    def __init__(self, model, *, max_tokens=3000):
        if not 256 <= max_tokens <= 8192:
            raise ValueError("invalid planner output token limit")
        self.agent = Agent(name="DataQueryPlanner", instructions=PLANNER_PROMPT, model=model,
                           output_type=PlannerDecision,
                           model_settings=ModelSettings(max_tokens=max_tokens, temperature=0, store=False))

    async def decide(self, packet):
        result = await Runner.run(self.agent, json.dumps(packet, ensure_ascii=False), max_turns=1,
                                  run_config=RunConfig(tracing_disabled=True))
        return result.final_output
