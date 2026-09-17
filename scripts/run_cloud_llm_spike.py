"""One real model call. Save prompt/output/errors, without credentials or reference data."""
import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from uteki.infrastructure.research_data.cloud_llm import PROMPT, VERSION, VALIDATOR_VERSION, materialize, prepare
from uteki.infrastructure.research_data.cloud_spike import CloudReader, digest, encoded, simulate

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--replay-run", type=Path, help="Revalidate a saved response without a model call")
    args = parser.parse_args()
    bundle, manifest, blocks = prepare(ROOT / "data/source_documents/alphabet_2025_10k")
    request = {"model": args.model, "messages": [{"role": "system", "content": PROMPT},
               {"role": "user", "content": encoded(bundle).decode()}],
               "temperature": 0, "max_tokens": 6000, "response_format": {"type": "json_object"}}
    started = datetime.now(timezone.utc).isoformat()
    run = {"started_at": started, "method": "llm_extraction", "model": args.model,
           "prompt_version": VERSION, "extractor_version": VERSION,
           "validator_version": VALIDATOR_VERSION,
           "request_sha256": digest(encoded(request)), "prompt_sha256": digest(PROMPT.encode()),
           "source_sha256": bundle["source_sha256"], "index_id": bundle["index_id"],
           "selected_node_ids": bundle["selected_node_ids"],
           "selected_block_ids": [b["block_id"] for b in bundle["blocks"]],
           "code_sha256": digest((ROOT / "src/uteki/infrastructure/research_data/cloud_llm.py").read_bytes()),
           "limitations": ["single filing, bounded literal retrieval", "not autonomous analysis",
                           "reference pending human review", "source checks do not prove semantic completeness"]}
    if args.replay_run:
        run["replayed_from"] = args.replay_run.name
    run_id = "run-" + digest(encoded(run))[:16]
    folder = ROOT / "data/research_data/google_cloud_spike" / run_id
    folder.mkdir(parents=True, exist_ok=False)
    def save(name, data):
        with (folder / name).open("xb") as stream:
            stream.write(encoded(data))
    save("input.json", bundle)
    save("request.json", request)
    diagnostics = []
    try:
        if args.prepare_only:
            run["status"] = "prepared"
        else:
            if args.replay_run:
                if (args.replay_run / "request.json").read_bytes() != encoded(request):
                    raise ValueError("replay request changed")
                response_bytes = (args.replay_run / "response.raw.json").read_bytes()
                origin = json.loads((args.replay_run / "run.json").read_text())
                run["model_called_at"] = origin.get("model_called_at", origin["started_at"])
                run["new_model_calls"] = 0
            else:
                if args.env_file is None:
                    raise ValueError("--env-file required for live execution")
                key = None
                for line in args.env_file.read_text().splitlines():
                    name, sep, value = line.strip().partition("=")
                    if sep and name.removeprefix("export ").strip() == "DEEPSEEK_API_KEY":
                        key = value.strip().strip("\"'")
                if not key:
                    raise ValueError("DeepSeek credential unavailable")
                req = urllib.request.Request("https://api.deepseek.com/v1/chat/completions",
                        data=json.dumps(request).encode(), method="POST",
                        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
                run["model_called_at"] = started
                run["new_model_calls"] = 1
                with urllib.request.urlopen(req, timeout=180) as response:
                    response_bytes = response.read()
            # Preserve the exact body even if JSON/content validation fails.
            with (folder / "response.raw.json").open("xb") as stream:
                stream.write(response_bytes)
            response = json.loads(response_bytes)
            run["response_sha256"] = digest(response_bytes)
            run["resolved_model"] = response.get("model")
            run["usage"] = response.get("usage")
            choice = response["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise ValueError("model did not complete normally")
            output = json.loads(choice["message"]["content"])
            save("output.json", output)
            snapshot = materialize(output, bundle, manifest, blocks)
            trace = simulate(CloudReader(snapshot, as_of=snapshot["available_at"]))
            save("snapshot.json", snapshot)
            save("trace.json", trace)
            run.update(status="candidate", snapshot_id=snapshot["snapshot_id"])
    except Exception as exc:
        # Never log request headers, credential files, or provider error bodies.
        diagnostic = {"type": type(exc).__name__}
        if isinstance(exc, urllib.error.HTTPError):
            diagnostic["http_status"] = exc.code
        elif isinstance(exc, ValueError):
            diagnostic["message"] = str(exc)[:180]
        diagnostics.append(diagnostic)
        run["status"] = "failed"
    run["finished_at"] = datetime.now(timezone.utc).isoformat()
    save("diagnostics.json", diagnostics)
    save("run.json", run)
    print(json.dumps({"run_id": run_id, "status": run["status"], "diagnostics": diagnostics,
                      "input_blocks": len(bundle["blocks"]), "request_bytes": len(encoded(request))}, indent=2))
    if run["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
