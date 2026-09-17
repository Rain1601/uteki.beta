from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from uteki.agents.research_archive import ArchiveError, Store
from uteki.agents.research_archive_context import build_context, freeze_context, read_history


def row(identifier, month):
    timestamp = f"2025-{month:02d}-01T00:00:00Z"
    return {"id": identifier, "company_id": "alphabet", "researcher_id": "single-default", "scope": "company-drivers",
            "primary_document_id": identifier + "-doc", "material_available_at": timestamp,
            "knowledge_cutoff_at": timestamp, "run_started_at": timestamp,
            "answer": f"Answer {identifier}", "validation_status": "passed"}


class ResearchArchiveContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "state.json")
        self.store.seed([row("old", 2), row("new", 5), row("candidate", 6)])
        self.store.act("old", "adopt", 1)
        self.store.act("new", "adopt", 1)

    def context(self):
        return build_context(self.store, "alphabet", "company-drivers", "2099-01-01")

    def test_only_baseline_answer_loaded_history_is_directory(self):
        context = self.context()
        self.assertEqual(context["baseline"]["content"]["answer"], "Answer new")
        self.assertEqual(context["history_snapshot_ids"], ["old"])
        self.assertNotIn("answer", context["history_directory"][0])
        self.assertEqual(context["integration_status"], "prepared_not_an_analysis_execution")

    def test_opinions_are_frozen_pending_not_truth(self):
        self.store.act("new", "comment", 2, text="More important", carry_forward=True)
        context = self.context()
        self.assertEqual(context["opinions"][0]["review_status"], "pending")
        original = deepcopy(context)
        self.store.act("new", "archive", 3)
        self.assertEqual(context, original)
        self.assertEqual(context["baseline_snapshot_id"], "new")
        self.assertEqual(self.context()["baseline_snapshot_id"], "old")

    def test_freeze_does_not_overwrite(self):
        context = self.context()
        output = freeze_context(context, self.root / "run")
        self.assertEqual(json.loads(output.read_text()), context)
        original = output.read_bytes()
        with self.assertRaises(ArchiveError):
            freeze_context(context, self.root / "run")
        self.assertEqual(original, output.read_bytes())
        self.assertEqual(list((self.root / "run").iterdir()), [output])

    def test_simultaneous_freeze_has_one_winner(self):
        context = self.context()
        def freeze(_):
            try:
                freeze_context(context, self.root / "run")
                return True
            except ArchiveError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(freeze, range(2))), 1)
        self.assertEqual(json.loads((self.root / "run/context_manifest.json").read_text()), context)

    def test_read_history_uses_frozen_allowlist_not_paths(self):
        context = self.context()
        result = read_history(context, self.store, "old")
        self.assertEqual(result["content"]["answer"], "Answer old")
        for denied in ("new", "candidate", str(self.root / "state.json"), "../../etc/passwd"):
            with self.assertRaises(ArchiveError):
                read_history(context, self.store, denied)

    def test_archived_history_refused_manifest_unchanged(self):
        context = self.context()
        original = deepcopy(context)
        self.store.act("old", "archive", 2)
        with self.assertRaises(ArchiveError):
            read_history(context, self.store, "old")
        self.assertEqual(context, original)

    def test_comment_change_warns_without_reading_new_opinion(self):
        context = self.context()
        self.store.act("old", "comment", 2, text="new opinion", carry_forward=True)
        result = read_history(context, self.store, "old")
        self.assertEqual(result["status"], "loaded_with_warning")
        self.assertNotIn("comments", result["content"])
        self.assertEqual(context["opinions"], [])

    def test_strict_future_analysis_absent(self):
        self.store.seed([{**row("backfilled", 8), "run_started_at": "2026-01-01T00:00:00Z"}])
        self.store.act("backfilled", "adopt", 1)
        context = build_context(self.store, "alphabet", "company-drivers", "2025-12-31")
        self.assertEqual(context["baseline_snapshot_id"], "new")
        self.assertNotIn("backfilled", context["history_snapshot_ids"])

    def test_empty_context_is_explicit(self):
        context = build_context(self.store, "alphabet", "company-drivers", "2024-01-01")
        self.assertIsNone(context["baseline"])
        self.assertEqual(context["history_directory"], [])


if __name__ == "__main__":
    unittest.main()
