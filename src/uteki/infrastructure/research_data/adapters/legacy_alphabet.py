"""Scope gate for the historical Alphabet FY2025 release/spike adapters."""


def require_legacy_alphabet_source(manifest):
    if (manifest.get("content_sha256") != "c2f6301004f35411a20611c14ff01d80a85c0bcbab6053c80d8cc7f6fc747161"
            or manifest.get("form") != "10-K" or manifest.get("period_end") != "2025-12-31"):
        raise ValueError("legacy Alphabet FY2025 adapter requires its pinned source; select another adapter")
