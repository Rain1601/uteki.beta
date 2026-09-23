"""Adversarial tool-output mutations must not redefine frozen package evidence."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from uteki.infrastructure.research_data.evidence_packaging import build_evidence_package
from uteki.infrastructure.research_data.financial_records import digest
from uteki.infrastructure.research_data.query_dataset import save
from uteki.infrastructure.research_data.query_service import QueryDataPort
from tests.unit.test_scoped_query_service import make_scoped_dataset


class EvidencePackagingIntegrityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        make_scoped_dataset(self.folder)
        self.port = QueryDataPort(self.folder)
        self.addCleanup(self.port.close)
        self.scope = {"snapshot_id": self.port.snapshot_id, "company_ids": ["acme"],
                      "source_snapshot_ids": ["acme-annual"], "source_policy_id": "local-frozen-v1",
                      "knowledge_cutoff": "2032-06-01", "include_candidates": True}

    @staticmethod
    def result(scope, context):
        context_id = "ctx-" + digest([context["source_snapshot_id"], context.get("block_ids"), context["blocks"]])[:24]
        return {"request": {"question": "Read the explicitly selected business section.", "scope": scope},
                "contexts": [{"context_id": context_id, **context}], "records": [], "computed_facts": [],
                "evidence": {}, "navigation": [], "gaps": []}

    def test_mutated_returned_body_cannot_become_source_verified_via_reader_cache(self):
        scoped = self.port.scoped(self.scope)
        context = scoped.read_source({"source_snapshot_id": "acme-annual", "node_id": "business",
                                      "start_block_id": "b1", "count": 1})
        frozen = self.folder / "indexes/acme-annual/blocks.jsonl"
        before = frozen.read_bytes()
        context["blocks"][0]["text"] = "Invented revenue of 999 trillion."
        with self.assertRaises(ValueError):
            build_evidence_package(scoped, self.result(self.scope, context))
        self.assertEqual(frozen.read_bytes(), before)

    def test_mutated_returned_source_descriptor_cannot_move_future_evidence_before_cutoff(self):
        scope = {**self.scope, "source_snapshot_ids": ["acme-future"]}
        scoped = self.port.scoped(scope)
        request = {"source_snapshot_id": "acme-future", "node_id": "business",
                   "start_block_id": "b1", "count": 1}
        blocked = scoped.read_source(request)
        self.assertEqual(blocked["status"], "not_available_at_cutoff")
        frozen = self.folder / "sources.json"
        before = frozen.read_bytes()
        # Responses currently expose the cached source dictionary. Mutating it
        # must not change the packaging authority even if another tool trusts it.
        blocked["source"]["available_at"] = "2030-01-01"
        context = scoped.read_source(request)
        if context["status"] == "read":
            with self.assertRaises(ValueError):
                build_evidence_package(scoped, self.result(scope, context))
        else:
            # Also allow a stronger tool implementation that never shares the
            # source dictionary and therefore rejects the read before assembly.
            self.assertEqual(context["status"], "not_available_at_cutoff")
        self.assertEqual(frozen.read_bytes(), before)
        source = next(s for s in json.loads(before) if s["source_snapshot_id"] == "acme-future")
        self.assertEqual(source["available_at"], "2033-02-01")

    def image_result(self, asset_id, assets):
        """Create a new hash-pinned synthetic image fixture before opening it."""
        folder = self.folder / "indexes/acme-annual"
        blocks = [json.loads(line) for line in (folder / "blocks.jsonl").read_text().splitlines()]
        blocks[1].update(type="image", image_asset_id=asset_id)
        (folder / "blocks.jsonl").write_text("".join(json.dumps(block) + "\n" for block in blocks))
        index_manifest = json.loads((folder / "manifest.json").read_text())
        index_manifest["artifacts"]["blocks.jsonl"]["sha256"] = digest((folder / "blocks.jsonl").read_bytes())
        save(folder / "manifest.json", index_manifest)
        save(folder / "assets.json", {"assets": assets})
        manifest_path = self.folder / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"] = {str(path.relative_to(self.folder)): digest(path.read_bytes())
                             for path in self.folder.rglob("*") if path.is_file() and path != manifest_path}
        save(manifest_path, manifest)
        port = QueryDataPort(self.folder)
        self.addCleanup(port.close)
        scoped = port.scoped(self.scope)
        context = scoped.read_source({"source_snapshot_id": "acme-annual", "node_id": "business",
                                      "start_block_id": "b1", "count": 1})
        return scoped, self.result(self.scope, context)

    def test_missing_or_blank_image_identity_never_selects_an_unbound_asset(self):
        for asset_id in (None, "", " ", " image-1 "):
            with self.subTest(asset_id=asset_id):
                asset = {"filename": "unbound.jpg", "source_url": "https://example.invalid/unbound.jpg"}
                if asset_id is not None:
                    asset["asset_id"] = asset_id
                scoped, result = self.image_result(asset_id, [asset])
                package = build_evidence_package(scoped, result)
                image = next(a["payload"] for a in package["artifacts"] if a["kind"] == "image_reference")
                self.assertIsNone(image["image_asset_id"])
                self.assertIsNone(image["asset_metadata"])
                self.assertEqual(image["bytes_status"], "unresolved")
                self.assertIsNone(image["bytes_sha256"])

    def test_existing_external_asset_path_is_never_read_or_marked_verified(self):
        with tempfile.TemporaryDirectory() as external_dir:
            external = Path(external_dir) / "external.jpg"
            external_bytes = b"Synthetic external image bytes"
            external.write_bytes(external_bytes)
            source_folder = self.folder / "indexes/acme-annual"
            paths = (str(external), os.path.relpath(external, source_folder))
            original_read_bytes = Path.read_bytes

            def refuse_external_read(path):
                if path.resolve() == external.resolve():
                    raise AssertionError("Packaging attempted to read an asset outside the selected dataset")
                return original_read_bytes(path)

            for local_path in paths:
                with self.subTest(local_path=local_path):
                    asset = {"asset_id": "image-1", "filename": external.name, "local_path": local_path,
                             "mime_type": "image/jpeg", "sha256": digest(external_bytes)}
                    scoped, result = self.image_result("image-1", [asset])
                    with patch.object(Path, "read_bytes", refuse_external_read):
                        package = build_evidence_package(scoped, result)
                    image = next(a["payload"] for a in package["artifacts"] if a["kind"] == "image_reference")
                    self.assertEqual(image["asset_metadata"], asset)
                    self.assertEqual(image["bytes_status"], "metadata_only")
                    self.assertIsNone(image["bytes_sha256"])
            self.assertEqual(external.read_bytes(), external_bytes)


if __name__ == "__main__":
    unittest.main()
