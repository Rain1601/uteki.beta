"""Run one bounded Analysis Agent experiment against an approved data snapshot."""
import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from uteki.agents.cloud_analysis import AnalysisTools, PROMPT, QUESTION, VERSION, load_approved, run_agent
from uteki.infrastructure.research_data.cloud_spike import digest, encoded
from uteki.agents.cloud_recovery import RecoveryTools, RECOVERY_PROMPT, VERSION as RECOVERY_VERSION
from uteki.infrastructure.research_data.cloud_recovery import withhold_fact

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--gap", action="store_true", help="Controlled A1 fixture: withhold FY2025 revenue, recover from source")
    parser.add_argument("--data-run", type=Path, default=ROOT / "data/research_data/google_cloud_spike/run-9856300a8d74fa77")
    args = parser.parse_args()
    snapshot, review = load_approved(args.data_run)
    parent_sha = digest(encoded(snapshot))
    if args.gap:
        snapshot = withhold_fact(snapshot)
    prompt = RECOVERY_PROMPT if args.gap else PROMPT
    started = datetime.now(timezone.utc).isoformat()
    run = {"started_at": started, "agent_version": RECOVERY_VERSION if args.gap else VERSION, "question": QUESTION,
           "model": args.model, "as_of": snapshot["available_at"], "input_run_id": args.data_run.name,
           "snapshot_id": snapshot["snapshot_id"], "snapshot_sha256": digest(encoded(snapshot)),
           "source_snapshot_id": snapshot["source_snapshot_id"], "approval_id": review["review_id"],
           "prompt_sha256": digest(prompt.encode()),
           "code_sha256": digest((ROOT / "src/uteki/agents/cloud_analysis.py").read_bytes()),
           "limits": {"model_rounds": 12, "tool_calls": 40, "calls_per_round": 8},
           "protocol": "model-generated JSON actions, allowlisted local dispatcher",
           "human_review": "pending", "limitations": ["No document retrieval", "No Thesis or causal attribution",
               "Narrative is model-authored and not automatically semantically verified", "Single approved snapshot"]}
    if args.gap:
        run.update(fixture={"kind": "controlled_missing_fact", "predicate": "revenue", "period": "FY2025",
                            "parent_snapshot_sha256": parent_sha},
                   approval_scope="parent input only; synthetic fixture and recovered overlay are unapproved",
                   limitations=["Controlled missing-data fixture", "Fixed source-only rule recovery; not general document search",
                                "Recovered facts and analysis pending review", "No Thesis or causal attribution"])
        run["recovery_code_sha256"] = {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in
            (ROOT / "src/uteki/agents/cloud_recovery.py", ROOT / "src/uteki/infrastructure/research_data/cloud_recovery.py")}
    run_id = "analysis-" + digest(encoded(run))[:16]
    folder = ROOT / "experiments/cloud_analysis" / run_id
    folder.mkdir(parents=True, exist_ok=False)
    def save(name, value):
        with (folder / name).open("xb") as f:
            f.write(encoded(value))
    save("input_snapshot.json", snapshot)
    save("input_review.json", review)
    tools = (RecoveryTools(snapshot, run["as_of"], ROOT / "data/source_documents/alphabet_2025_10k") if args.gap else
             AnalysisTools(snapshot, run["as_of"]))
    rounds, diagnostics = [], []
    key = None
    try:
        for line in args.env_file.read_text().splitlines():
            name, sep, value = line.strip().partition("=")
            if sep and name.removeprefix("export ").strip() == "DEEPSEEK_API_KEY":
                key = value.strip().strip("\"'")
        if not key:
            raise ValueError("DeepSeek credential unavailable")
        def complete(messages):
            number = len(rounds) + 1
            request = {"model": args.model, "messages": messages, "temperature": 0,
                       "max_tokens": 3500, "response_format": {"type": "json_object"}}
            save(f"round-{number:02d}-request.json", request)
            entry = {"round": number, "started_at": datetime.now(timezone.utc).isoformat(),
                     "request_sha256": digest(encoded(request))}
            rounds.append(entry)
            req = urllib.request.Request("https://api.deepseek.com/v1/chat/completions", method="POST",
                    data=json.dumps(request).encode(),
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as response:
                raw = response.read()
            with (folder / f"round-{number:02d}-response.json").open("xb") as f:
                f.write(raw)
            response = json.loads(raw)
            entry.update(finished_at=datetime.now(timezone.utc).isoformat(),
                         response_sha256=digest(raw), model=response.get("model"), usage=response.get("usage"))
            choice = response["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise ValueError("model response not complete")
            action = json.loads(choice["message"]["content"])
            entry["action"] = action
            print(f"Round {number}: {action.get('action')}", flush=True)
            return action
        answer = run_agent(complete, tools, prompt=prompt)
        save("answer.json", answer)
        run["status"] = "candidate"
    except Exception as exc:
        diagnostic = {"type": type(exc).__name__}
        if isinstance(exc, urllib.error.HTTPError):
            diagnostic["http_status"] = exc.code
        elif isinstance(exc, ValueError):
            diagnostic["message"] = str(exc)[:220]
        diagnostics.append(diagnostic)
        run["status"] = "failed"
    save("trace.json", tools.trace)
    if args.gap:
        save("resolved_snapshot.json", tools.resolved_snapshot())
    save("comparisons.json", tools.comparisons)
    save("rounds.json", rounds)
    save("diagnostics.json", diagnostics)
    run.update(finished_at=datetime.now(timezone.utc).isoformat(), model_calls=len(rounds), tool_calls=len(tools.trace))
    save("run.json", run)
    print(json.dumps({"run_id": run_id, "status": run["status"], "model_calls": len(rounds),
                      "tool_calls": len(tools.trace), "diagnostics": diagnostics}, indent=2))
    if run["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
