"""Small natural-language query canary. Explicit config, immutable artifacts."""
import argparse
import asyncio
import json
from decimal import Decimal
from pathlib import Path
import sys

from uteki.agents.analysis_comparison import model_adapter
from uteki.agents.call_costs import MeteredModel, pricing_snapshot, summarize
from uteki.agents.data_query_agent import DataQueryAgent, PLANNER_PROMPT, write_new
from uteki.agents.data_query_model import SdkQueryPlanner, check_prior_budgets
from uteki.agents.local_credentials import load_provider_key
from uteki.agents.run_budget import RunBudget
from uteki.domain.research_data.agent_query import AgentQuery
from uteki.infrastructure.research_data.financial_records import digest
from uteki.infrastructure.research_data.query_service import QueryDataPort

ROOT = Path(__file__).resolve().parents[1]


def preflight(config):
    approval = config.get("prior_unknown_cost_acknowledgment")
    allowed = []
    if approval:
        if approval["policy"] != "retain_unknown_and_allow_bounded_new_run" or Decimal(config["budget_usd"]) > Decimal(approval["new_budget_usd"]):
            raise ValueError("canary exceeds the explicit prior-cost acknowledgment")
        allowed = [{**item, "path": ROOT / item["path"]} for item in approval["unknowns"]]
    return check_prior_budgets([ROOT / p for p in config["prior_budgets"]], acknowledged_unknowns=allowed)


def prepare(config_path, output):
    config = json.loads(config_path.read_text())
    if not config["prior_budgets"]:
        raise ValueError("declare the prior experiment budget ledgers explicitly")
    limit = Decimal(config["budget_usd"])
    if (not limit.is_finite() or limit <= 0 or not 1 <= config["max_steps"] <= 12
            or not 256 <= config["max_tokens"] <= 8192):
        raise ValueError("invalid canary execution limits")
    if not 1 <= len(config["cases"]) <= 4:
        raise ValueError("canary requires 1..4 cases; inspect results before expanding")
    if not 1 <= config["max_requests_total"] <= 12:
        raise ValueError("first canary is limited to 12 total requests across run folders")
    for case in config["cases"]:
        if set(case) != {"id", "request"} or not case["id"].replace("-", "").isalnum():
            raise ValueError("case contains unexpected inputs or an invalid ID")
        AgentQuery.model_validate(case["request"])
    if len({c['id'] for c in config['cases']}) != len(config['cases']):
        raise ValueError("duplicate case ID")
    pricing = pricing_snapshot(config["provider"], config["model"])
    if not pricing:
        raise ValueError("no checked pricing for requested provider/model")
    with QueryDataPort(ROOT / config["dataset"]) as port:
        if any(c["request"]["snapshot_id"] != port.snapshot_id for c in config["cases"]):
            raise ValueError("case snapshot mismatch")
        dataset_manifest_hash = digest((port.dataset / "manifest.json").read_bytes())
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / "config.json", config)
    write_new(output / "preflight.json", preflight(config))
    files = [Path(__file__).resolve(), ROOT / "src/uteki/agents/data_query_agent.py",
             ROOT / "src/uteki/agents/data_query_model.py", ROOT / "src/uteki/domain/research_data/agent_query.py",
             ROOT / "src/uteki/agents/analysis_comparison.py", ROOT / "src/uteki/agents/deepseek_model.py",
             ROOT / "src/uteki/agents/call_costs.py", ROOT / "src/uteki/agents/run_budget.py",
             ROOT / "src/uteki/infrastructure/research_data/query_service.py"]
    files.extend([ROOT / "src/uteki/domain/research_data/period_scope.py",
                  ROOT / "src/uteki/agents/document_reader.py"])
    write_new(output / "manifest.json", {"config_sha256": digest(config), "dataset_manifest_sha256": dataset_manifest_hash,
              "code_hashes": {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in files},
              "prompt": PLANNER_PROMPT, "pricing": pricing, "model_calls": 0,
              "scope": "First canary only. No reference answers or prewritten plans are supplied to the model."})


async def execute(prepared, output):
    config = json.loads((prepared / "config.json").read_text())
    manifest = json.loads((prepared / "manifest.json").read_text())
    if digest(config) != manifest["config_sha256"]:
        raise ValueError("prepared config changed")
    for name, expected in manifest["code_hashes"].items():
        if digest((ROOT / name).read_bytes()) != expected:
            raise ValueError("prepared implementation changed; prepare a new run")
    if digest((ROOT / config["dataset"] / "manifest.json").read_bytes()) != manifest["dataset_manifest_sha256"]:
        raise ValueError("dataset manifest changed")
    gate = preflight(config)
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / "preflight.json", gate)
    if gate["status"] == "blocked":
        result = {"status": "blocked_prior_unknown_cost", "model_calls": 0,
                  "detail": "Prior budget must be reconciled before billable execution."}
        write_new(output / "result.json", result)
        return result
    load_provider_key(ROOT, config["provider"])
    budget = RunBudget(ROOT / config["budget_ledger"], config["budget_usd"])
    rows = []
    with QueryDataPort(ROOT / config["dataset"]) as port:
        for case in config["cases"]:
            remaining_requests = config["max_requests_total"] - budget.summary()["requests"]
            if remaining_requests <= 0:
                break
            folder = output / case["id"]
            folder.mkdir()
            inner = model_adapter(config["model"], config["provider"])
            metered = MeteredModel(inner, folder / "calls", "data_query_planner", config["provider"],
                                  config["model"], manifest["pricing"], budget)
            agent = DataQueryAgent(port, SdkQueryPlanner(metered, max_tokens=config["max_tokens"]),
                                   max_steps=min(config["max_steps"], remaining_requests))
            result = await agent.run(case["request"], output=folder / "session")
            costs = summarize(folder / "calls")
            write_new(folder / "costs.json", costs)
            rows.append({"id": case["id"], "status": result["status"], "costs": costs})
            print(case["id"], result["status"], flush=True)
            if budget.summary()["unknown_requests"] or result["status"] in ("failed", "limited"):
                break
    result = {"status": "canary_needs_review", "cases": rows, "budget": budget.summary(),
              "scope": "Do not expand until the saved plans, outputs and evidence pass source review."}
    write_new(output / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    prep = subs.add_parser("prepare")
    prep.add_argument("--config", type=Path, required=True)
    prep.add_argument("--output", type=Path, required=True)
    run = subs.add_parser("run")
    run.add_argument("--prepared", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.config, args.output)
    else:
        result = asyncio.run(execute(args.prepared, args.output))
        print(json.dumps({k: v for k, v in result.items() if k != "cases"}, ensure_ascii=False))
        return 2 if result["status"] == "blocked_prior_unknown_cost" or any(
            c["status"] in ("failed", "limited") for c in result.get("cases", [])) else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
