from concurrent.futures import ThreadPoolExecutor
import json
import multiprocessing
from pathlib import Path
import tempfile
import unittest

from uteki.agents.research_archive import ArchiveError, ConflictError, Store


def sample(identifier="a", **overrides):
    row = dict(id=identifier, company_id="alphabet", researcher_id="single-default", scope="company-drivers", primary_document_id="10k-2024",
               material_available_at="2025-02-01T00:00:00Z", knowledge_cutoff_at="2025-02-01T00:00:00Z",
               run_started_at="2025-02-02T00:00:00Z", validation_status="passed", answer="original")
    row.update(overrides)
    return row


def adopt_in_process(path, identifier, queue):
    try:
        Store(path).act(identifier, "adopt", 1)
        queue.put("adopted")
    except ConflictError:
        queue.put("conflict")


class ResearchArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "archive.json"
        self.store = Store(self.path)

    def test_seed_idempotent_and_no_implicit_adoption(self):
        self.store.seed([sample()])
        self.store.seed([sample(answer="must not overwrite")])
        self.assertEqual(self.store.list()[0]["answer"], "original")
        self.assertEqual(self.store.list()[0]["status"], "candidate")
        self.assertEqual(len(json.loads(self.path.read_text())["audit_events"]), 1)
        with self.assertRaises(ArchiveError):
            self.store.seed([sample("b", status="adopted")])

    def test_adoption_preserves_candidates_and_revision_conflicts(self):
        self.store.seed([sample(), sample("b"), sample("c", scope="cloud")])
        result = self.store.act("a", "adopt", 1)
        self.assertEqual({row["id"] for row in result["changed"]}, {"a"})
        with self.assertRaises(ConflictError):
            self.store.act("a", "archive", 1)
        with self.assertRaises(ConflictError):
            self.store.act("b", "adopt", 1)
        self.store.act("c", "adopt", 1)
        self.store.act("a", "archive", 2)
        self.store.act("b", "adopt", 1)

    def test_failed_validation_cannot_be_adopted(self):
        self.store.seed([sample(validation_status="failed")])
        before = self.path.read_bytes()
        with self.assertRaises(ArchiveError):
            self.store.act("a", "adopt", 1)
        self.assertEqual(self.path.read_bytes(), before)

    def test_inferred_primary_requires_explicit_confirmation(self):
        self.store.seed([sample(primary_inferred=True)])
        with self.assertRaises(ArchiveError):
            self.store.act("a", "adopt", 1)
        with self.assertRaises(ArchiveError):
            self.store.act("a", "adopt", 1, confirm_primary="true")
        result = self.store.act("a", "adopt", 1, confirm_primary=True)
        self.assertIsNotNone(result["snapshot"]["primary_confirmed_at"])

    def test_delete_restore_cannot_restore_context_privileges(self):
        self.store.seed([sample()])
        self.store.act("a", "adopt", 1)
        with self.assertRaises(ArchiveError):
            self.store.act("a", "delete", 2)
        self.store.act("a", "archive", 2)
        self.store.act("a", "delete", 3)
        self.store.act("a", "restore", 4)
        self.assertEqual(self.store.list()[0]["status"], "archived")
        self.assertIsNone(self.store.context("alphabet", "company-drivers", "2026-01-01")["baseline_snapshot_id"])

    def test_edit_preserves_source_and_requires_validation(self):
        self.store.seed([sample()])
        result = self.store.act("a", "edit", 1, answer="changed", human_notes="why")
        edited = result["snapshot"]
        original = next(row for row in self.store.list() if row["id"] == "a")
        self.assertEqual(original["answer"], "original")
        self.assertEqual(edited["parent_snapshot_id"], "a")
        self.assertEqual(edited["validation_status"], "pending")
        with self.assertRaises(ArchiveError):
            self.store.act(edited["id"], "adopt", 1)
        self.store.act(edited["id"], "review", 1, review_notes="Verified cited source and human revision")
        self.store.act(edited["id"], "adopt", 2)
        revision = self.store.act(edited["id"], "edit", 3, answer="new draft")["snapshot"]
        self.assertEqual(revision['status'], 'candidate')
        self.assertEqual(next(r for r in self.store.list() if r['id']==edited['id'])['status'], 'adopted')

    def test_failed_parent_cannot_be_fixed_by_notes(self):
        self.store.seed([sample(validation_status="failed", citation_errors=["unread evidence"])])
        edited = self.store.act("a", "edit", 1, human_notes="I prefer it")["snapshot"]
        with self.assertRaises(ArchiveError):
            self.store.act(edited["id"], "review", 1, review_notes="I approve")

    def test_sort_material_before_execution(self):
        self.store.seed([sample("old", run_started_at="2026-12-01T00:00:00Z"),
                         sample("new", primary_document_id="10q-2025", material_available_at="2025-05-01T00:00:00Z"),
                         sample("old2", run_started_at="2026-12-01T00:00:00Z")])
        self.assertEqual([row["id"] for row in self.store.list()], ["new", "old2", "old"])

    def test_context_cutoff_and_latest_not_all(self):
        self.store.seed([sample(), sample("later", primary_document_id="q2", material_available_at="2025-05-01T00:00:00Z",
                                         knowledge_cutoff_at="2025-05-01T00:00:00Z", run_started_at="2025-05-02T00:00:00Z")])
        self.store.act("a", "adopt", 1)
        self.store.act("later", "adopt", 1)
        earlier = self.store.context("alphabet", "company-drivers", "2025-03-01")
        self.assertEqual(earlier["baseline_snapshot_id"], "a")
        current = self.store.context("alphabet", "company-drivers", "2025-06-01")
        self.assertEqual(current["loaded_snapshot_ids"], ["later"])
        self.assertEqual(current["history_snapshot_ids"], ["a"])
        self.store.act("a", "archive", 2)
        self.assertEqual(current["history_snapshot_ids"], ["a"])  # previously frozen manifest is unchanged
        self.assertEqual(self.store.context("alphabet", "company-drivers", "2025-06-01")["history_snapshot_ids"], [])

    def test_strict_excludes_future_analysis(self):
        self.store.seed([sample(run_started_at="2026-02-01T00:00:00Z")])
        self.store.act("a", "adopt", 1)
        self.assertIsNone(self.store.context("alphabet", "company-drivers", "2025-12-01")["baseline_snapshot_id"])
        self.assertEqual(self.store.context("alphabet", "company-drivers", "2025-12-01", strict=False)["baseline_snapshot_id"], "a")

    def test_comments_version_and_withdrawal(self):
        self.store.seed([sample()])
        self.store.act("a", "adopt", 1)
        added = self.store.act("a", "comment", 2, text="Services is more important", carry_forward=True)
        opinion = added["snapshot"]["comments"][0]
        self.assertEqual(opinion["kind"], "unclassified")
        context = self.store.context("alphabet", "company-drivers", "2099-01-01")
        self.assertEqual(context["opinions"][0]["review_status"], "pending")
        self.assertEqual(context["opinions"][0]["epistemic_role"], "human_input_not_verified_fact")
        self.store.act("a", "edit_comment", 3, comment_id=opinion["comment_id"], text="Services profits matter", kind="hypothesis")
        self.store.act("a", "withdraw_opinion", 4, opinion_id=opinion["comment_id"])
        self.assertEqual(self.store.context("alphabet", "company-drivers", "2099-01-01")["opinions"], [])
        history = json.loads(self.path.read_text())["comments"][opinion["comment_id"]]
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]["text"], "Services is more important")

    def test_comments_not_automatically_carried_or_available_in_past(self):
        self.store.seed([sample()])
        self.store.act("a", "adopt", 1)
        self.store.act("a", "comment", 2, text="An opinion", carry_forward=False)
        self.assertEqual(self.store.context("alphabet", "company-drivers", "2099-01-01")["opinions"], [])
        self.store.act("a", "comment", 3, text="A selected opinion", carry_forward=True)
        self.assertEqual(self.store.context("alphabet", "company-drivers", "2025-12-01")["opinions"], [])

    def test_inherited_opinion_keeps_identity_and_withdrawal_marks_descendants(self):
        self.store.seed([sample()])
        self.store.act("a", "adopt", 1)
        opinion = self.store.act("a", "comment", 2, text="Check incremental profit", carry_forward=True)["snapshot"]["comments"][0]
        self.store.seed([sample("next", primary_document_id="q2", material_available_at="2025-05-01T00:00:00Z",
                                knowledge_cutoff_at="2025-05-01T00:00:00Z", baseline_snapshot_id="a",
                                inherited_comment_refs=[{"comment_id": opinion["comment_id"], "version": 1}])])
        self.store.act("next", "adopt", 1)
        context = self.store.context("alphabet", "company-drivers", "2099-01-01")
        self.assertEqual(context["opinions"][0]["comment_id"], opinion["comment_id"])
        self.store.act("a", "withdraw_comment", 3, comment_id=opinion["comment_id"])
        self.assertTrue(next(row for row in self.store.list() if row["id"] == "next")["inheritance_review_required"])
        self.assertEqual(self.store.context("alphabet", "company-drivers", "2099-01-01")["opinions"], [])

    def test_concurrent_adoption_only_one_winner(self):
        self.store.seed([sample(), sample("b")])
        def adopt(identifier):
            try:
                Store(self.path).act(identifier, "adopt", 1)
                return True
            except ConflictError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(adopt, ["a", "b"]))
        self.assertEqual(sum(results), 1)
        self.assertEqual(sum(row["status"] == "adopted" for row in self.store.list()), 1)

    def test_unknown_timestamp_does_not_enter_context(self):
        self.store.seed([sample(material_available_at=None)])
        with self.assertRaises(ArchiveError):
            self.store.act("a", "adopt", 1)

    def test_processes_share_adoption_lock(self):
        self.store.seed([sample(), sample("b")])
        context = multiprocessing.get_context("fork")
        queue = context.Queue()
        processes = [context.Process(target=adopt_in_process, args=(self.path, identifier, queue)) for identifier in ("a", "b")]
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=5)
            self.assertEqual(process.exitcode, 0)
        self.assertEqual(sorted([queue.get(timeout=1), queue.get(timeout=1)]), ["adopted", "conflict"])
        state = json.loads(self.path.read_text())
        self.assertEqual(len(state["audit_events"]), 2)
        self.assertEqual(len(state["audit_events"][-1]["changes"]), 1)
        queue.close()

    def test_sort_compares_actual_instants_not_timezone_strings(self):
        self.store.seed([sample("earlier", primary_document_id="x", material_available_at="2025-03-01T08:00:00+08:00"),
                         sample("later", primary_document_id="y", material_available_at="2025-03-01T01:00:00Z")])
        self.assertEqual(self.store.list()[0]["id"], "later")


if __name__ == "__main__":
    unittest.main()
