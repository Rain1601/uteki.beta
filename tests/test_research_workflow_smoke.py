from contextlib import redirect_stdout
import hashlib
import importlib.util
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/smoke_research_workflow.py"
spec = importlib.util.spec_from_file_location("research_workflow_smoke", SCRIPT)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def workspace_state():
    """Include newly created production artifacts, not just the five input files."""
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for folder in ("data", "benchmarks") for path in (ROOT / folder).rglob("*") if path.is_file()}


class ResearchWorkflowSmokeTests(unittest.TestCase):
    def fixture_copy(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for relative in smoke.INPUT_FILES.values():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        return root

    def change(self, root, name, mutate):
        path = root / smoke.INPUT_FILES[name]
        value = json.loads(path.read_text())
        mutate(value)
        path.write_text(json.dumps(value), encoding="utf-8")

    def test_real_store_workflow_keeps_workspace_and_original_report_unchanged(self):
        before = workspace_state()
        result = smoke.run_smoke()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["source_snapshot_id"], "alphabet-2025-10k-c2f63010")
        self.assertEqual(result["counts"]["claims"], 1)
        self.assertEqual(result["counts"]["exact_quote_spans"], 1)
        self.assertEqual(result["input_counts"]["claims"], 42)
        self.assertEqual(result["scope"], {"mode": "selected_claim", "claim_ids": ["alphabet-definition"],
                                         "evidence_ids": ["e-overview"], "paragraph_ordinals": [55]})
        self.assertFalse(result["all_candidate_chains_validated"])
        self.assertEqual(result["full_excerpt_hash_check"], "failed")
        self.assertEqual([item["paragraph_ordinal"] for item in result["integrity_findings"]], [90])
        self.assertFalse(result["integrity_findings"][0]["in_verified_scope"])
        self.assertEqual(result["workflow"]["actions"], ["seed", "edit", "review", "adopt"])
        self.assertEqual(result["workflow"]["snapshots_after_reload"], 2)
        for check in ("unreviewed_adoption_rejected_without_write", "original_report_preserved",
                      "revision_history_preserved", "baseline_requires_explicit_adoption",
                      "candidate_and_reviewed_revision_excluded_from_baseline", "simulation_only"):
            self.assertTrue(result["workflow"][check], check)
        self.assertTrue(result["temporary_archive_removed"])
        self.assertTrue(any("not semantic support" in value for value in result["limitations"]))
        self.assertEqual(workspace_state(), before)

    def test_tampered_excerpt_rejected_even_when_stored_hashes_still_match(self):
        root = self.fixture_copy()
        self.change(root, "excerpt", lambda value: value["paragraphs"][0].update(text="Tampered source text"))
        with self.assertRaisesRegex(smoke.SmokeError, "Excerpt text hash mismatch"):
            smoke.run_smoke(root)

    def test_missing_cited_paragraph_rejected(self):
        root = self.fixture_copy()
        self.change(root, "excerpt", lambda value: value["paragraphs"].pop(0))
        with self.assertRaisesRegex(smoke.SmokeError, "Missing excerpt paragraph"):
            smoke.run_smoke(root)

    def test_missing_claim_evidence_and_missing_span_rejected(self):
        for scenario in ("evidence", "span"):
            with self.subTest(scenario=scenario):
                root = self.fixture_copy()
                if scenario == "evidence":
                    self.change(root, "claims", lambda value: value["claims"][0]["evidence_ids"].append("missing-evidence"))
                    message = "missing evidence"
                else:
                    self.change(root, "spans", lambda value: value["spans"].pop(0))
                    message = "Missing claim/evidence span"
                with self.assertRaisesRegex(smoke.SmokeError, message):
                    smoke.run_smoke(root)

    def test_quote_must_match_original_english_excerpt(self):
        root = self.fixture_copy()
        self.change(root, "spans", lambda value: value["spans"][0].update(quote_en="Invented quotation"))
        with self.assertRaisesRegex(smoke.SmokeError, "not an exact excerpt substring"):
            smoke.run_smoke(root)

    def test_failure_is_structured_and_nonzero(self):
        root = self.fixture_copy()
        (root / smoke.INPUT_FILES["excerpt"]).unlink()
        output = StringIO()
        with redirect_stdout(output):
            status = smoke.main([], root=root)
        self.assertEqual(status, 1)
        failure = json.loads(output.getvalue())
        self.assertEqual(failure["status"], "failed")
        self.assertEqual(failure["error_type"], "FileNotFoundError")

    def test_strict_all_fails_on_known_committed_excerpt_corruption(self):
        before = workspace_state()
        output = StringIO()
        with redirect_stdout(output):
            status = smoke.main(["--strict-all"])
        self.assertEqual(status, 1)
        self.assertIn("Excerpt text hash mismatch at paragraph 90", json.loads(output.getvalue())["error"])
        self.assertEqual(workspace_state(), before)

    def test_direct_script_runs_from_unrelated_working_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            environment.pop("PYTHONPATH", None)
            result = subprocess.run([sys.executable, "-B", str(SCRIPT)], cwd=temporary,
                                    env=environment, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "passed")
            self.assertEqual(list(Path(temporary).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
