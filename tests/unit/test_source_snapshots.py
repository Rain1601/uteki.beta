from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from uteki.infrastructure.document_sources import snapshots
from uteki.infrastructure.document_sources.sec import parse_sec_html


URL = "https://www.example.test/filings/123/report.htm"
WHEN = "2026-09-18T09:00:00+00:00"
RETRIEVAL = {"method": "local_import", "requested_url": URL, "network_performed": False}
HTML = (b"<!doctype html><html><body><div>Example Inc.</div>"
        b"<p>Revenue was 100.</p><div><img src='chart.jpg'/></div>"
        b"<div><img src='https://www.example.test/filings/123/chart.jpg'/></div>"
        b"<div><img src='images/logo.png'/></div></body></html>")
ASSETS = {"chart.jpg": b"original-chart-bytes", "logo.png": b"original-logo-bytes"}
SEC_URL = "https://www.sec.gov/Archives/edgar/data/1652044/000165204426000018/goog-20251231.htm"
PIXEL_URL = "https://www.sec.gov/akam/13/pixel_3f5f58ec?a=dD0xJmpzPW9mZg=="
PIXEL_STYLE = "visibility: hidden; position: absolute; left: -999px; top: -999px;"


def source_manifest(raw=HTML):
    document = parse_sec_html("example-123", URL, raw)
    contract = "".join(f"{p.ordinal}:{p.text_hash}\n" for p in document.paragraphs)
    return {"document_id": document.id, "source_url": URL,
            "source_snapshot_id": "historical-snapshot", "company": "Example Inc.",
            "form": "10-K", "period_end": "2025-12-31", "filed_at": "2026-02-05",
            "accession": "0000000001-26-000001", "parser_version": "sec-visible-blocks-v1",
            "content_sha256": hashlib.sha256(raw).hexdigest(),
            "paragraph_count": len(document.paragraphs),
            "paragraph_contract_sha256": hashlib.sha256(contract.encode()).hexdigest(),
            "raw_document_committed": False}


class SourceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "candidate"

    def make(self, *, raw=HTML, expected=None, assets=None, output=None):
        return snapshots.import_snapshot(
            raw, source_manifest=source_manifest() if expected is None else expected,
            assets=ASSETS if assets is None else assets,
            output_dir=self.output if output is None else output,
            retrieved_at=WHEN, retrieval=RETRIEVAL,
        )

    def write_manifest(self, value):
        (self.output / "manifest.json").write_text(json.dumps(value), encoding="utf-8")

    def test_round_trip_preserves_raw_and_expectations_without_promoting_approval(self):
        expected = source_manifest()
        before = deepcopy(expected)
        manifest = self.make(expected=expected)
        self.assertEqual(expected, before)
        self.assertEqual(manifest["status"], "candidate")
        self.assertNotEqual(manifest["source_snapshot_id"], expected["source_snapshot_id"])
        self.assertEqual(manifest["legacy_source_manifest"], before)
        self.assertTrue(manifest["legacy_comparison"]["matches_legacy"])
        self.assertTrue(manifest["legacy_comparison"]["paragraph_count_matches"])
        self.assertTrue(manifest["legacy_comparison"]["paragraph_contract_matches"])
        self.assertEqual(manifest["image_reference_count"], 3)
        self.assertEqual(len(manifest["assets"]), 2)
        self.assertEqual(gzip.decompress((self.output / "source.html.gz").read_bytes()), HTML)
        self.assertEqual((self.output / "source.html.gz").read_bytes()[4:8], b"\0" * 4)
        self.assertEqual(snapshots.verify_snapshot(self.output), manifest)
        expected_document = parse_sec_html(expected["document_id"], URL, HTML)
        self.assertEqual(snapshots.load_snapshot_document(self.output), expected_document)
        self.assertEqual(json.loads((self.output / "document.json").read_text()),
                         json.loads(json.dumps(asdict(expected_document))))
        for name, item in manifest["artifacts"].items():
            raw = (self.output / name).read_bytes()
            self.assertEqual(item, {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})

    def test_different_source_bytes_become_a_new_candidate_with_explicit_mismatches(self):
        original = source_manifest()
        raw = HTML.replace(b"Revenue was 100.", b"Revenue was 200.</p><p>New disclosure.")
        manifest = self.make(raw=raw, expected=original)
        comparison = manifest["legacy_comparison"]
        self.assertFalse(comparison["matches_legacy"])
        self.assertFalse(comparison["paragraph_count_matches"])
        self.assertFalse(comparison["paragraph_contract_matches"])
        self.assertEqual(original, source_manifest())
        self.assertEqual(snapshots.verify_snapshot(self.output), manifest)

    def test_optional_expectations_are_unknown_and_not_claimed_as_matches(self):
        manifest = self.make(expected={"document_id": "caller-id", "source_url": URL})
        for key in ("matches_legacy", "paragraph_count_matches", "paragraph_contract_matches"):
            self.assertIsNone(manifest["legacy_comparison"][key])
        self.assertEqual(snapshots.load_snapshot_document(self.output).id, "caller-id")

    def test_explicit_legacy_contract_expectation_is_supported_without_raw_identity_match(self):
        expected = source_manifest()
        expected["expected_legacy_paragraph_contract_sha256"] = expected.pop("paragraph_contract_sha256")
        # A byte change outside visible blocks changes the file, not the legacy text.
        raw = HTML.replace(b"<html>", b"<html lang='en'>")
        manifest = self.make(raw=raw, expected=expected)
        self.assertFalse(manifest["legacy_comparison"]["matches_legacy"])
        self.assertTrue(manifest["legacy_comparison"]["paragraph_contract_matches"])
        self.assertTrue(manifest["legacy_comparison"]["paragraph_count_matches"])
        snapshots.verify_snapshot(self.output)

    def test_same_inputs_are_byte_stable_and_changed_attachment_changes_identity(self):
        first = self.make()
        second_path = self.root / "second"
        second = self.make(output=second_path)
        self.assertEqual(first, second)
        for path in self.output.rglob("*"):
            if path.is_file():
                self.assertEqual(path.read_bytes(), (second_path / path.relative_to(self.output)).read_bytes())
        changed = self.make(assets={**ASSETS, "chart.jpg": b"different-chart"}, output=self.root / "third")
        self.assertNotEqual(first["source_snapshot_id"], changed["source_snapshot_id"])

    def test_existing_directory_is_never_overwritten_even_when_empty(self):
        self.output.mkdir()
        with self.assertRaises(FileExistsError):
            self.make()
        self.assertEqual(list(self.output.iterdir()), [])
        sentinel = self.output / "manifest.json"
        sentinel.write_bytes(b"existing")
        with self.assertRaises(FileExistsError):
            self.make()
        self.assertEqual(sentinel.read_bytes(), b"existing")

    def test_missing_or_unreferenced_assets_fail_before_creating_a_candidate(self):
        for assets in ({"chart.jpg": ASSETS["chart.jpg"]}, {**ASSETS, "extra.jpg": b"extra"}):
            with self.subTest(assets=list(assets)), self.assertRaises(snapshots.SnapshotError):
                self.make(assets=assets)
            self.assertFalse(self.output.exists())

    def test_unsafe_image_sources_are_rejected_before_writing(self):
        references = ["https://other.test/filings/123/chart.jpg", "http://www.example.test/filings/123/chart.jpg",
                      "//www.example.test/filings/123/chart.jpg", "../chart.jpg", "%2e%2e/chart.jpg",
                      "%252e%252e/chart.jpg", "images%2fchart.jpg", "images\\chart.jpg",
                      "/filings/other/chart.jpg", "chart.jpg?version=2", "chart.jpg#part",
                      "https://user:password@www.example.test/filings/123/chart.jpg",
                      "https://www.example.test:444/filings/123/chart.jpg", "data:image/png;base64,AA"]
        for reference in references:
            raw = f"<div>Source</div><img src='{reference}'>".encode()
            with self.subTest(reference=reference), self.assertRaises(snapshots.SnapshotError):
                self.make(raw=raw, assets={"chart.jpg": b"image"})
            self.assertFalse(self.output.exists())

    def test_same_filename_collisions_and_ambiguous_image_policies_are_rejected(self):
        bodies = ["<img src='one/chart.jpg'><img src='two/chart.jpg'>",
                  "<img src='Chart.jpg'><img src='chart.jpg'>",
                  "<img src='chart.jpg' src='other.jpg'>", "<img>", "<img src=''>",
                  "<img src='chart.jpg' srcset='other.jpg 2x'>", "<base href='https://other.test/'>"]
        for body in bodies:
            with self.subTest(body=body), self.assertRaises(snapshots.SnapshotError):
                self.make(raw=("<div>Source</div>" + body).encode())
            self.assertFalse(self.output.exists())

    def test_filing_relative_and_absolute_paths_can_reference_one_attachment(self):
        raw = ("<div>Source</div><img src='./chart.jpg'>"
               "<img src='/filings/123/chart.jpg'>"
               "<img src='https://WWW.EXAMPLE.TEST:443/filings/123/chart.jpg'>").encode()
        manifest = self.make(raw=raw, assets={"chart.jpg": b"image"})
        self.assertEqual(len(manifest["assets"]), 1)
        self.assertEqual(manifest["image_reference_count"], 3)
        snapshots.verify_snapshot(self.output)

    def test_no_images_needs_no_attachment_and_remains_verifiable(self):
        self.make(raw=b"<div>Source without images.</div>", assets={})
        self.assertFalse((self.output / "assets").exists())
        snapshots.verify_snapshot(self.output)

    def test_known_sec_tracking_pixel_is_recorded_separately_and_raw_bytes_are_preserved(self):
        raw = (f"<html><body><div>SEC source</div><img src='chart.jpg'>"
               f"<noscript><img src='{PIXEL_URL}' style='{PIXEL_STYLE}' /></noscript>"
               "</body></html>").encode()
        manifest = self.make(raw=raw, assets={"chart.jpg": ASSETS["chart.jpg"]},
                             expected={"document_id": "sec-filing", "source_url": SEC_URL, "form": "10-K"})
        self.assertEqual(manifest["image_reference_count"], 2)
        self.assertEqual(manifest["excluded_image_reference_count"], 1)
        self.assertEqual([item["filename"] for item in manifest["assets"]], ["chart.jpg"])
        excluded = manifest["excluded_image_references"][0]
        self.assertEqual(excluded["image_reference_ordinal"], 2)
        self.assertEqual(excluded["source_path"], PIXEL_URL)
        self.assertEqual(excluded["reason"], "sec_akamai_noscript_tracking_pixel")
        self.assertEqual(gzip.decompress((self.output / "source.html.gz").read_bytes()), raw)
        self.assertEqual(snapshots.verify_snapshot(self.output), manifest)
        modified = deepcopy(manifest)
        modified["excluded_image_references"] = []
        self.write_manifest(modified)
        with self.assertRaises(snapshots.SnapshotError):
            snapshots.verify_snapshot(self.output)

    def test_hidden_and_noscript_content_images_still_require_complete_asset_coverage(self):
        for body in (f"<img src='chart.jpg' style='{PIXEL_STYLE}'>",
                     "<noscript><img src='chart.jpg'></noscript>"):
            with self.subTest(body=body):
                raw = ("<div>Disclosure</div>" + body).encode()
                with self.assertRaisesRegex(snapshots.SnapshotError, "coverage mismatch"):
                    self.make(raw=raw, assets={})
                output = self.root / ("content-" + str(len(body)))
                manifest = self.make(raw=raw, assets={"chart.jpg": b"disclosed-chart"}, output=output)
                self.assertEqual(manifest["excluded_image_reference_count"], 0)
                self.assertEqual(len(manifest["assets"]), 1)
                snapshots.verify_snapshot(output)

    def test_tracking_exception_requires_the_known_host_endpoint_context_and_style(self):
        cases = [
            (PIXEL_URL, PIXEL_STYLE, False, SEC_URL),
            (PIXEL_URL, "visibility: visible;", True, SEC_URL),
            (PIXEL_URL, PIXEL_STYLE, True, URL),
            (PIXEL_URL.replace("www.sec.gov/", "other.test/"), PIXEL_STYLE, True, SEC_URL),
            (PIXEL_URL.replace("pixel_3f5f58ec", "different.jpg"), PIXEL_STYLE, True, SEC_URL),
            (PIXEL_URL + "&unexpected=1", PIXEL_STYLE, True, SEC_URL),
            (PIXEL_URL, "visibility:hidden;position:absolute;left:-999px;malformed", True, SEC_URL),
        ]
        for url, style, noscript, source_url in cases:
            with self.subTest(url=url, style=style, noscript=noscript, source_url=source_url):
                image = f"<img src='{url}' style='{style}'>"
                body = f"<noscript>{image}</noscript>" if noscript else image
                with self.assertRaises(snapshots.SnapshotError):
                    self.make(raw=("<div>Source</div>" + body).encode(), assets={},
                              expected={"document_id": "filing", "source_url": source_url})
                self.assertFalse(self.output.exists())

    def test_write_failure_does_not_publish_a_manifest_or_partial_snapshot(self):
        write = snapshots._write_new
        def fail_on_document(path, raw):
            if path.name == "document.json":
                path.write_bytes(raw[:10])
                raise OSError("simulated disk failure")
            write(path, raw)
        with patch.object(snapshots, "_write_new", side_effect=fail_on_document):
            with self.assertRaisesRegex(OSError, "disk failure"):
                self.make()
        self.assertFalse(self.output.exists())

    def test_manifest_write_failure_does_not_leave_a_published_candidate(self):
        write = snapshots._write_new
        def fail_on_manifest(path, raw):
            if path.name == ".manifest.json.tmp":
                path.write_bytes(raw[:10])
                raise OSError("simulated manifest failure")
            write(path, raw)
        with patch.object(snapshots, "_write_new", side_effect=fail_on_manifest):
            with self.assertRaisesRegex(OSError, "manifest failure"):
                self.make()
        self.assertFalse(self.output.exists())

    def test_each_stored_artifact_is_checked_before_loading(self):
        for artifact in ("source.html.gz", "document.json", "assets/chart.jpg"):
            with self.subTest(artifact=artifact):
                path = self.root / artifact.replace("/", "-")
                self.make(output=path)
                (path / artifact).write_bytes(b"tampered")
                with self.assertRaises(snapshots.SnapshotError):
                    snapshots.load_snapshot_document(path)

    def test_resealing_a_modified_document_cannot_bypass_source_reparsing(self):
        manifest = self.make()
        path = self.output / "document.json"
        document = json.loads(path.read_text())
        document["paragraphs"][0]["text"] = "Unsupported statement"
        path.write_bytes(snapshots._json_bytes(document))
        manifest["artifacts"]["document.json"] = {"bytes": path.stat().st_size,
                                                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        self.write_manifest(manifest)
        with self.assertRaisesRegex(snapshots.SnapshotError, "reparsed"):
            snapshots.verify_snapshot(self.output)

    def test_top_level_metadata_and_comparison_cannot_disagree_with_expectations(self):
        original = self.make()
        for key, value in (("form", "10-Q"), ("source_url", "https://other.test/report.htm"),
                           ("source_snapshot_id", "historical-snapshot"), ("content_sha256", "0" * 64),
                           ("paragraph_count", 900), ("status", "frozen"),
                           ("legacy_comparison", {"matches_legacy": False})):
            with self.subTest(key=key):
                modified = {**original, key: value}
                self.write_manifest(modified)
                with self.assertRaises(snapshots.SnapshotError):
                    snapshots.verify_snapshot(self.output)

    def test_missing_and_extra_files_and_symlink_assets_are_rejected(self):
        self.make()
        extra = self.output / "untracked.txt"
        extra.write_text("untracked")
        with self.assertRaises(snapshots.SnapshotError):
            snapshots.verify_snapshot(self.output)
        extra.unlink()
        asset = self.output / "assets/chart.jpg"
        raw = asset.read_bytes()
        asset.unlink()
        with self.assertRaises(snapshots.SnapshotError):
            snapshots.verify_snapshot(self.output)
        outside = self.root / "outside.jpg"
        outside.write_bytes(raw)
        asset.symlink_to(outside)
        with self.assertRaises(snapshots.SnapshotError):
            snapshots.verify_snapshot(self.output)

    def test_invalid_metadata_and_timestamps_fail_before_writing(self):
        for updates in ({"source_url": "http://www.example.test/report.htm"},
                        {"content_sha256": "invalid"}, {"paragraph_count": True},
                        {"document_id": ""}, {"form": None},
                        {"expected_legacy_paragraph_contract_sha256": "0" * 64}):
            with self.subTest(updates=updates), self.assertRaises(snapshots.SnapshotError):
                self.make(expected={**source_manifest(), **updates})
        with self.assertRaises(snapshots.SnapshotError):
            snapshots.import_snapshot(HTML, source_manifest=source_manifest(), assets=ASSETS,
                                      output_dir=self.output, retrieved_at="2026-09-18", retrieval={})
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
