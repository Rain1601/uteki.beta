"""Existing metered model adapters used as a single-decision planner."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3

from agents import Agent, ModelSettings, Runner, RunConfig

from uteki.domain.research_data.agent_query import PlannerDecision
from uteki.domain.research_data.scoped_agent_query import ScopedPlannerDecision
from uteki.domain.research_data.task_plan import TaskPlannerDecision, TaskPlanProposal
from .prompts import PLANNER_PROMPT, SCOPED_PLANNER_PROMPT, TASK_PLANNER_PROMPT, TASK_PROPOSAL_PROMPT


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
    plan_origin = "model"

    def __init__(self, model, *, max_tokens=3000, scoped=False, task_mode=False):
        if not 256 <= max_tokens <= 8192:
            raise ValueError("invalid planner output token limit")
        if scoped and task_mode:
            raise ValueError('Choose one planner contract')
        self.agent = Agent(name="DataQueryPlanner", instructions=TASK_PLANNER_PROMPT if task_mode else SCOPED_PLANNER_PROMPT if scoped else PLANNER_PROMPT, model=model,
                           output_type=TaskPlannerDecision if task_mode else ScopedPlannerDecision if scoped else PlannerDecision,
                           model_settings=ModelSettings(max_tokens=max_tokens, temperature=0, store=False))
        self.proposer = Agent(name='TaskPlanProposer', instructions=TASK_PROPOSAL_PROMPT, model=model,
            output_type=TaskPlanProposal, model_settings=ModelSettings(max_tokens=max_tokens, temperature=0, store=False)) if task_mode else None

    async def draft_plan(self, packet):
        if self.proposer is None:
            raise ValueError('Task proposal requires task_mode')
        result = await Runner.run(self.proposer, json.dumps(packet, ensure_ascii=False), max_turns=1,
                                 run_config=RunConfig(tracing_disabled=True))
        return result.final_output

    async def decide(self, packet):
        result = await Runner.run(self.agent, json.dumps(packet, ensure_ascii=False), max_turns=1,
                                  run_config=RunConfig(tracing_disabled=True))
        return result.final_output
