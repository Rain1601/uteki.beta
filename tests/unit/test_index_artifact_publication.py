from __future__ import annotations

import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from uteki.infrastructure.document_sources.index_artifacts import build_index_artifacts
from uteki.infrastructure.document_sources.snapshots import SnapshotError, import_snapshot, verify_snapshot


# A small JPEG marker fixture: SOI, a baseline frame (2 x 1), and EOI. This
# exercises the indexer's dimension reader without a binary fixture dependency.
JPEG = b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x02\x01\x01\x11\x00\xff\xd9"
SOURCE = b"""<!doctype html><html><body>
<div style="font-weight:700">PART I</div>
<div style="font-weight:700">ITEM 1. BUSINESS</div>
<p>A business with a disclosed chart.</p><img src="chart.jpg" alt="chart">
<div style="font-weight:700">ITEM 1A. RISK FACTORS</div>
<p>Risk disclosure.</p></body></html>"""


class IndexArtifactPublicationTests(unittest.TestCase):
    def _snapshot(self, root: Path) -> Path:
        snapshot = root / "source-snapshots" / "new-source"
        (snapshot / "assets").mkdir(parents=True)
        (snapshot / "source.html.gz").write_bytes(gzip.compress(SOURCE, mtime=0))
        (snapshot / "assets" / "chart.jpg").write_bytes(JPEG)
        (snapshot / "manifest.json").write_text(json.dumps({
            "document_id": "synthetic-filing",
            "source_url": "https://example.test/report.html",
            "source_snapshot_id": "synthetic-source-1",
            "form": "10-K",
            "content_sha256": hashlib.sha256(SOURCE).hexdigest(),
        }), encoding="utf-8")
        return snapshot

    def _verified_snapshot(self, root: Path, *, tracking_pixel: bool = False) -> Path:
        snapshot = root / "verified-snapshot"
        source = SOURCE
        if tracking_pixel:
            source = source.replace(b"</body>", (
                b'<noscript><img src="https://www.sec.gov/akam/13/pixel_3f5f58ec?a=dD0xJmpzPW9mZg==" '
                b'style="visibility: hidden; position: absolute; left: -999px; top: -999px;" />'
                b'</noscript></body>'
            ))
        import_snapshot(
            source,
            source_manifest={
                "document_id": "synthetic-filing",
                "source_url": "https://www.sec.gov/Archives/edgar/data/1/2/report.htm",
                "form": "10-K",
            },
            assets={"chart.jpg": JPEG}, output_dir=snapshot,
            retrieved_at="2026-09-18T09:00:00+00:00", retrieval={"method": "synthetic_fixture"},
        )
        return snapshot

    def test_external_index_resolves_assets_in_the_actual_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = self._snapshot(root)
            output = root / "review-packages" / "v0.2" / "document-index"
            manifest = build_index_artifacts(snapshot, output)
            assets = json.loads((output / "assets.json").read_text())["assets"]
            self.assertEqual(len(assets), 1)
            asset = assets[0]
            self.assertEqual((output / asset["local_path"]).resolve(), (snapshot / "assets/chart.jpg").resolve())
            self.assertEqual((asset["width"], asset["height"]), (2, 1))
            self.assertEqual(asset["sha256"], hashlib.sha256(JPEG).hexdigest())
            self.assertFalse(Path(asset["local_path"]).is_absolute())
            for filename, entry in manifest["artifacts"].items():
                content = (output / filename).read_bytes()
                self.assertEqual(hashlib.sha256(content).hexdigest(), entry["sha256"])
                self.assertEqual(len(content), entry["bytes"])
            self.assertEqual(json.loads((output / "manifest.json").read_text()), manifest)
            self.assertEqual(manifest["source_verification"], "legacy_html_hash_only")

    def test_new_snapshot_is_fully_verified_and_tracking_pixel_is_not_a_filing_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = self._verified_snapshot(root, tracking_pixel=True)
            source_manifest = json.loads((snapshot / "manifest.json").read_text())
            output = root / "index"
            manifest = build_index_artifacts(snapshot, output, parser_version="sec-source-blocks-v0.1.5")
            self.assertEqual(manifest["source_verification"], "complete_snapshot")
            self.assertEqual(manifest["source_snapshot_id"], source_manifest["source_snapshot_id"])
            self.assertEqual(source_manifest["excluded_image_reference_count"], 1)
            self.assertEqual(manifest["counts"]["images"], 1)
            asset = json.loads((output / "assets.json").read_text())["assets"][0]
            self.assertEqual(asset["filename"], "chart.jpg")
            self.assertEqual((output / asset["local_path"]).resolve(), (snapshot / "assets/chart.jpg").resolve())

    def test_incompatible_parser_cannot_silently_treat_tracking_as_filing_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = self._verified_snapshot(root, tracking_pixel=True)
            output = root / "index"
            with self.assertRaisesRegex(ValueError, "excluded tracking pixel"):
                build_index_artifacts(snapshot, output, parser_version="sec-source-blocks-v0.1.1")
            self.assertFalse(output.exists())

    def test_new_index_cannot_add_untracked_files_inside_a_verified_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            snapshot = self._verified_snapshot(Path(temporary))
            original = verify_snapshot(snapshot)
            output = snapshot / "indexes" / "v0.1-candidate"
            with self.assertRaisesRegex(ValueError, "outside the verified source snapshot"):
                build_index_artifacts(snapshot, output)
            self.assertFalse(output.exists())
            self.assertEqual(verify_snapshot(snapshot), original)

    def test_changed_attachment_cannot_be_indexed_under_the_old_snapshot_identity(self) -> None:
        for reseal in (False, True):
            with self.subTest(reseal=reseal), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                snapshot = self._verified_snapshot(root)
                changed = JPEG + b"changed attachment"
                (snapshot / "assets/chart.jpg").write_bytes(changed)
                if reseal:
                    manifest_path = snapshot / "manifest.json"
                    manifest = json.loads(manifest_path.read_text())
                    entry = {"bytes": len(changed), "sha256": hashlib.sha256(changed).hexdigest()}
                    manifest["assets"][0].update(entry)
                    manifest["artifacts"]["assets/chart.jpg"] = entry
                    manifest_path.write_text(json.dumps(manifest))
                output = root / "index"
                with self.assertRaises(SnapshotError):
                    build_index_artifacts(snapshot, output)
                self.assertFalse(output.exists())

    def test_new_snapshot_document_and_schema_are_verified_before_publication(self) -> None:
        for mutation in ("document", "remove_schema", "unknown_schema"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                snapshot = self._verified_snapshot(root)
                if mutation == "document":
                    (snapshot / "document.json").write_text("{}")
                else:
                    manifest_path = snapshot / "manifest.json"
                    manifest = json.loads(manifest_path.read_text())
                    if mutation == "remove_schema":
                        del manifest["schema_version"]
                    else:
                        manifest["schema_version"] = "source-snapshot-unknown"
                    manifest_path.write_text(json.dumps(manifest))
                output = root / "index"
                with self.assertRaises(SnapshotError):
                    build_index_artifacts(snapshot, output)
                self.assertFalse(output.exists())

    def test_conventional_nested_index_keeps_a_valid_relative_asset_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            snapshot = self._snapshot(Path(temporary))
            output = snapshot / "indexes" / "v0.1-candidate"
            build_index_artifacts(snapshot, output)
            asset = json.loads((output / "assets.json").read_text())["assets"][0]
            self.assertEqual(asset["local_path"], "../../assets/chart.jpg")

    def test_directory_name_cannot_promote_a_candidate_to_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = self._snapshot(root)
            for name in ("v0.1", "approved", "v0.1-candidate"):
                with self.subTest(name=name):
                    output = root / name
                    manifest = build_index_artifacts(snapshot, output)
                    self.assertEqual(manifest["status"], "candidate")
                    self.assertEqual(manifest["index_version"], name)

    def test_rebuild_does_not_change_existing_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = self._snapshot(root)
            output = root / "index"
            build_index_artifacts(snapshot, output)
            before = {path.name: path.read_bytes() for path in output.iterdir()}
            with self.assertRaises(FileExistsError):
                build_index_artifacts(snapshot, output)
            self.assertEqual({path.name: path.read_bytes() for path in output.iterdir()}, before)

    def test_even_empty_or_symlinked_output_is_not_reused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = self._snapshot(root)
            empty = root / "empty-index"
            empty.mkdir()
            dangling = root / "dangling-index"
            dangling.symlink_to(root / "missing-index", target_is_directory=True)
            for output in (empty, dangling):
                with self.subTest(output=output):
                    with self.assertRaises(FileExistsError):
                        build_index_artifacts(snapshot, output)
            self.assertEqual(list(empty.iterdir()), [])
            self.assertTrue(dangling.is_symlink())

    def test_invalid_source_does_not_publish_an_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = self._snapshot(root)
            (snapshot / "source.html.gz").write_bytes(gzip.compress(b"changed source"))
            output = root / "index"
            with self.assertRaisesRegex(ValueError, "manifest SHA"):
                build_index_artifacts(snapshot, output)
            self.assertFalse(output.exists())

    def test_missing_asset_does_not_publish_an_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = self._snapshot(root)
            (snapshot / "assets/chart.jpg").unlink()
            output = root / "index"
            with self.assertRaises(FileNotFoundError):
                build_index_artifacts(snapshot, output)
            self.assertFalse(output.exists())

    def test_artifact_write_failure_leaves_no_completion_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = self._snapshot(root)
            output = root / "index"
            original_open = Path.open

            def fail_block_write(path, *args, **kwargs):
                if path == output / "blocks.jsonl":
                    raise OSError("simulated artifact write failure")
                return original_open(path, *args, **kwargs)

            with patch.object(Path, "open", fail_block_write):
                with self.assertRaisesRegex(OSError, "artifact write failure"):
                    build_index_artifacts(snapshot, output)
            self.assertTrue((output / "index.json").exists())
            self.assertFalse((output / "manifest.json").exists())
            with self.assertRaises(FileExistsError):
                build_index_artifacts(snapshot, output)

    def test_manifest_is_published_after_all_artifacts_and_failure_is_not_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = self._snapshot(root)
            output = root / "index"

            def fail_publication(source, target):
                self.assertEqual(target, output / "manifest.json")
                self.assertFalse(target.exists())
                manifest = json.loads(source.read_text())
                for name, entry in manifest["artifacts"].items():
                    self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), entry["sha256"])
                raise OSError("simulated manifest publication failure")

            with patch("uteki.infrastructure.document_sources.index_artifacts.os.link", fail_publication):
                with self.assertRaisesRegex(OSError, "publication failure"):
                    build_index_artifacts(snapshot, output)
            self.assertFalse((output / "manifest.json").exists())
            self.assertEqual(list(output.glob(".manifest-*")), [])


if __name__ == "__main__":
    unittest.main()
