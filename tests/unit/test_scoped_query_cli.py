"""Source-scoped CLI/runner contracts, using temporary fixtures and no provider calls."""
import asyncio
from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
import unittest
import tempfile
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError

from scripts import run_data_agent_query as runner
from uteki.agents.data_query_agent import PLANNER_PROMPT, SCOPED_PLANNER_PROMPT
from uteki.agents.run_budget import RunBudget
from uteki.domain.research_data.agent_query import AgentQuery
from uteki.domain.research_data.scoped_agent_query import SCOPED_AGENT_VERSION, ScopedAgentQuery
from uteki.infrastructure.research_data.financial_records import digest
from uteki.infrastructure.research_data.query_cli import main as query_main
from tests.unit.test_scoped_query_service import make_scoped_dataset


PROJECT = Path(__file__).resolve().parents[2]


def scope():
    return {"execution_schema_version": "research-execution-v1", "snapshot_id": "synthetic-scoped-v1",
            "company_ids": ["acme"], "source_snapshot_ids": ["acme-annual"],
            "source_policy_id": "local-frozen-v1", "knowledge_cutoff": "2032-06-01", "include_candidates": True}


class ScopedQueryCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.dataset = self.root / "dataset"
        self.dataset.mkdir()
        make_scoped_dataset(self.dataset)
        self.scope_file = self.root / "scope.json"
        self.scope_file.write_text(json.dumps(scope()))

    def invoke(self, tool, payload=None, extra=(), output=None):
        args = [tool, "--dataset", str(self.dataset), "--scope", str(self.scope_file)]
        if payload is not None:
            request = self.root / "request.json"
            request.write_text(json.dumps(payload))
            args += ["--request", str(request)]
        args += list(extra)
        if output is not None:
            args = ["--out", str(output), *args]
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = query_main(args)
        content = stdout.getvalue() if status == 0 else stderr.getvalue()
        return status, json.loads(content) if content else None

    def test_all_scoped_commands_dispatch_to_real_scoped_tools(self):
        status, schema = self.invoke("scoped-schema")
        self.assertEqual(status, 0)
        self.assertEqual(schema["scope"]["source_snapshot_ids"], ["acme-annual"])
        self.assertIn("read_source", schema["execution_contracts"])
        status, discovery = self.invoke("scoped-discover")
        self.assertEqual(status, 0)
        self.assertEqual({s["source_snapshot_id"] for s in discovery["sources"]}, {"acme-annual"})

        headers = {k: scope()[k] for k in
                   ("snapshot_id", "source_policy_id", "knowledge_cutoff", "include_candidates")}
        status, data = self.invoke("scoped-query", {"query_id": "cli-test", **headers, "records": [{
            "entity_id": "acme-services", "metric_id": "revenue", "period": {
                "kind": "year", "start": "2031-01-01", "end": "2031-12-31"}}]})
        self.assertEqual(status, 0)
        self.assertEqual(data["records"][0]["value_decimal"], "100")
        self.assertEqual({r["source_snapshot_id"] for r in data["records"]}, {"acme-annual"})
        status, evidence = self.invoke("scoped-evidence", extra=["--id", data["records"][0]["evidence_ids"][0]])
        self.assertEqual(status, 0)
        self.assertEqual({e["source_snapshot_id"] for e in evidence["evidence"].values()}, {"acme-annual"})

        source = {"source_snapshot_id": "acme-annual"}
        status, outline = self.invoke("scoped-outline", source)
        self.assertEqual(status, 0)
        self.assertIn("business", {n["node_id"] for n in outline["nodes"]})
        status, read = self.invoke("scoped-read", {**source, "node_id": "business", "count": 3})
        self.assertEqual(status, 0)
        self.assertEqual(read["block_ids"], ["b0", "b1", "b2"])
        status, search = self.invoke("scoped-search", {**source, "node_id": "business", "phrase": "products"})
        self.assertEqual(status, 0)
        self.assertEqual(search["hits"][0]["block_id"], "b1")
        status, context = self.invoke("scoped-context", extra=["--source", "acme-annual", "--block", "b1"])
        self.assertEqual(status, 0)
        self.assertEqual(context["source_snapshot_id"], "acme-annual")
        self.assertEqual(context["blocks"][0]["text"], "acme sales from products.")

    def test_cli_refuses_missing_scope_or_excluded_source(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            query_main(["scoped-schema", "--dataset", str(self.dataset)])
        self.assertEqual(error.exception.code, 2)
        status, error = self.invoke("scoped-context", extra=["--source", "acme-amended", "--block", "b1"])
        self.assertEqual(status, 2)
        self.assertIn("outside execution scope", error["message"])
        self.scope_file.write_text(json.dumps({**scope(), "source_snapshot_ids": ["other-annual"]}))
        status, error = self.invoke("scoped-schema")
        self.assertEqual(status, 2)
        self.assertIn("company scope", error["message"])

    def test_existing_output_is_never_overwritten_or_used_as_read_permission(self):
        output = self.root / "result.json"
        original = b'{"preserve": true}\n'
        output.write_bytes(original)
        with patch("uteki.infrastructure.research_data.query_cli.QueryDataPort") as port:
            status, error = self.invoke("scoped-schema", output=output)
        port.assert_not_called()
        self.assertEqual(status, 2)
        self.assertEqual(error["error_type"], "FileExistsError")
        self.assertEqual(output.read_bytes(), original)

    def test_legacy_cli_schema_remains_available_without_new_scope_argument(self):
        output = io.StringIO()
        with redirect_stdout(output):
            status = query_main(["schema", "--dataset", str(self.dataset)])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue())["schema_version"], "research-query-v0.3")


class ScopedPreparedRunnerTests(unittest.TestCase):
    def test_cli_rejects_invalid_plan_with_failure_exit_code(self):
        result = {"status": "canary_needs_review", "cases": [{"status": "invalid_plan"}]}
        with patch("sys.argv", ["run_data_agent_query", "run", "--prepared", "unused", "--output", "unused"]), \
             patch.object(runner, "execute", AsyncMock(return_value=result)), redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main(), 2)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        # Hash actual code in an isolated layout. No credentials, original budgets
        # or workstation paths are copied into any test-generated config/artifact.
        shutil.copytree(PROJECT / "src/uteki", self.root / "src/uteki",
                        ignore=shutil.ignore_patterns("__pycache__"))
        (self.root / "scripts").mkdir()
        script = self.root / "scripts/run_data_agent_query.py"
        shutil.copyfile(PROJECT / "scripts/run_data_agent_query.py", script)
        dataset = self.root / "dataset"
        dataset.mkdir()
        make_scoped_dataset(dataset)
        self.enterContext(patch.object(runner, "ROOT", self.root))
        self.enterContext(patch.object(runner, "__file__", str(script)))
        self.provider = self.enterContext(patch.object(runner, "model_adapter",
            side_effect=AssertionError("offline test must not create a provider")))
        self.credentials = self.enterContext(patch.object(runner, "load_provider_key",
            side_effect=AssertionError("offline test must not load credentials")))
        RunBudget(self.root / "prior.sqlite", "1")
        self.config = {"agent_schema_version": SCOPED_AGENT_VERSION, "dataset": "dataset",
            "provider": "deepseek", "model": "deepseek-flash", "budget_usd": "1",
            "budget_ledger": "run-budget.sqlite", "prior_budgets": ["prior.sqlite"],
            "max_steps": 2, "max_tokens": 256, "max_requests_total": 2,
            "cases": [{"id": "source-review", "request": {"agent_schema_version": SCOPED_AGENT_VERSION,
                "question": "Read the selected Business chapter.", "scope": scope()}}]}

    def prepare(self, config=None, name="prepared"):
        config = self.config if config is None else config
        config_file = self.root / f"{name}-config.json"
        config_file.write_text(json.dumps(config))
        output = self.root / name
        runner.prepare(config_file, output)
        return output

    def test_request_version_dispatch_is_explicit_and_unknown_versions_rejected(self):
        self.assertIs(runner.request_contract({}), AgentQuery)
        self.assertIs(runner.request_contract({"agent_schema_version": "data-agent-query-v0.2"}), AgentQuery)
        self.assertIs(runner.request_contract(self.config), ScopedAgentQuery)
        for value in ("data-agent-query-v9", "", None):
            with self.subTest(version=value), self.assertRaises(ValueError):
                runner.request_contract({"agent_schema_version": value})
        unversioned = copy.deepcopy(self.config)
        del unversioned["agent_schema_version"]
        with self.assertRaises(ValidationError):
            self.prepare(unversioned)

    def test_prepare_validates_required_source_company_and_snapshot_scope(self):
        changes = [None, {**scope(), "source_snapshot_ids": []},
                   {**scope(), "source_snapshot_ids": ["unknown-source"]},
                   {**scope(), "source_snapshot_ids": ["other-annual"]},
                   {**scope(), "snapshot_id": "different-snapshot"}]
        for index, value in enumerate(changes):
            config = copy.deepcopy(self.config)
            if value is None:
                del config["cases"][0]["request"]["scope"]
            else:
                config["cases"][0]["request"]["scope"] = value
            with self.subTest(scope=value), self.assertRaises(ValueError):
                self.prepare(config, name=f"invalid-{index}")
            self.assertFalse((self.root / f"invalid-{index}").exists())
        self.credentials.assert_not_called()
        self.provider.assert_not_called()

    def test_prepare_pins_new_scope_contracts_reading_code_and_selected_prompt(self):
        prepared = self.prepare()
        frozen = json.loads((prepared / "config.json").read_text())
        self.assertEqual(frozen, self.config)
        manifest = json.loads((prepared / "manifest.json").read_text())
        self.assertEqual(manifest["prompt"], SCOPED_PLANNER_PROMPT)
        self.assertEqual(manifest["model_calls"], 0)
        required = {"src/uteki/domain/research_data/scoped_agent_query.py",
                    "src/uteki/domain/research_data/execution_scope.py",
                    "src/uteki/agents/reading/reading_groups.py", "src/uteki/agents/reading/document_reader.py",
                    "src/uteki/agents/data_query/agent.py", "src/uteki/agents/data_query/model.py",
                    "src/uteki/agents/data_query/prompts.py", "src/uteki/agents/data_query/artifacts.py",
                    "src/uteki/agents/runtime/model_factory.py",
                    "src/uteki/infrastructure/research_data/query_service.py", "scripts/run_data_agent_query.py"}
        self.assertTrue(required.issubset(manifest["code_hashes"]))
        for relative, expected in manifest["code_hashes"].items():
            self.assertFalse(Path(relative).is_absolute())
            self.assertEqual(digest((self.root / relative).read_bytes()), expected)
        self.credentials.assert_not_called()
        self.provider.assert_not_called()

    def test_runner_uses_matching_legacy_or_scoped_sdk_and_agent_entrypoint(self):
        for scoped in (False, True):
            with self.subTest(scoped=scoped):
                config = copy.deepcopy(self.config)
                if not scoped:
                    config.pop("agent_schema_version")
                    config["cases"][0]["request"] = {"question": "Acme Services margin in FY2031?",
                        **{key: value for key, value in scope().items()
                           if key not in ("execution_schema_version", "source_snapshot_ids")}}
                name = "scoped" if scoped else "legacy"
                prepared = self.prepare(config, name=name)
                manifest = json.loads((prepared / "manifest.json").read_text())
                self.assertEqual(manifest["prompt"], SCOPED_PLANNER_PROMPT if scoped else PLANNER_PROMPT)
                agent = SimpleNamespace(run=AsyncMock(return_value={"status": "answered"}),
                                        run_scoped=AsyncMock(return_value={"status": "answered"}))
                with patch.object(runner, "load_provider_key", return_value="mock") as credentials, \
                     patch.object(runner, "model_adapter", return_value=object()) as provider, \
                     patch.object(runner, "MeteredModel", return_value=object()), \
                     patch.object(runner, "SdkQueryPlanner", return_value=object()) as planner, \
                     patch.object(runner, "DataQueryAgent", return_value=agent), redirect_stdout(io.StringIO()):
                    result = asyncio.run(runner.execute(prepared, self.root / f"{name}-output"))
                self.assertEqual(result["status"], "canary_needs_review")
                self.assertEqual(planner.call_args.kwargs["scoped"], scoped)
                called, unused = (agent.run_scoped, agent.run) if scoped else (agent.run, agent.run_scoped)
                called.assert_awaited_once()
                unused.assert_not_awaited()
                self.assertEqual(called.call_args.args[0], config["cases"][0]["request"])
                credentials.assert_called_once()
                provider.assert_called_once()

    def test_changed_planner_implementation_invalidates_prepared_run(self):
        prepared = self.prepare()
        implementation = self.root / "src/uteki/agents/data_query/prompts.py"
        implementation.write_text(implementation.read_text() + "\n# changed planner\n")
        output = self.root / "changed-planner"
        with self.assertRaisesRegex(ValueError, "implementation changed"):
            asyncio.run(runner.execute(prepared, output))
        self.assertFalse(output.exists())
        self.credentials.assert_not_called()
        self.provider.assert_not_called()

    def test_changed_new_contract_invalidates_prepared_run_before_any_live_setup(self):
        prepared = self.prepare()
        contract = self.root / "src/uteki/domain/research_data/execution_scope.py"
        contract.write_bytes(contract.read_bytes() + b"\n# test-only change\n")
        output = self.root / "must-not-start"
        with patch.object(runner, "preflight") as preflight, self.assertRaisesRegex(ValueError, "implementation changed"):
            asyncio.run(runner.execute(prepared, output))
        preflight.assert_not_called()
        self.credentials.assert_not_called()
        self.provider.assert_not_called()
        self.assertFalse(output.exists())

    def test_original_v02_prepared_run_is_rejected_without_rewriting_or_loading_credentials(self):
        prepared = PROJECT / "experiments/data_agent_query/canary-v1/prepared-approved"
        before = {name: digest((prepared / name).read_bytes()) for name in ("config.json", "manifest.json")}
        output = self.root / "historical-must-not-run"
        with patch.object(runner, "ROOT", PROJECT), patch.object(runner, "preflight") as preflight, \
             self.assertRaisesRegex(ValueError, "implementation changed"):
            asyncio.run(runner.execute(prepared, output))
        preflight.assert_not_called()
        self.credentials.assert_not_called()
        self.provider.assert_not_called()
        self.assertFalse(output.exists())
        self.assertEqual(before, {name: digest((prepared / name).read_bytes()) for name in before})


if __name__ == "__main__":
    unittest.main()
