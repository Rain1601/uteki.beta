"""Freeze bounded research inputs; never resolve a history ID as a filesystem path.

Contexts must be server-built manifests, not arbitrary client-supplied allowlists.
No analysis provider is invoked here. Pending opinions are unverified human input.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile

from uteki.agents.archive.research_archive import ArchiveError, Store, _date


def _rerun_feedback(state, context, source_id):
    """An explicit rerun target is not an adopted annual baseline."""
    row = state['snapshots'].get(source_id)
    if row is None or row['status']=='deleted':
        raise ArchiveError('Rerun source unavailable')
    if (row['company_id'],row['scope'],row.get('researcher_id'),row['primary_document_id']) != (
        context['company_id'],context['scope'],context['researcher_id'],(context.get('current_material') or {}).get('id')):
        raise ArchiveError('Rerun source must match researcher, scope and current material')
    boundary=_date(context['cutoff'])
    if max(_date(row['material_available_at']),_date(row['knowledge_cutoff_at']))>boundary:
        raise ArchiveError('Rerun source contains material after cutoff')
    if context['strict'] and max(_date(row.get('created_at') or row['run_started_at']),_date(row['run_started_at']))>boundary:
        raise ArchiveError('Rerun source was authored after the strict cutoff')
    opinions,excluded=[],[]
    for versions in state['comments'].values():
        opinion=versions[-1]
        if opinion['snapshot_id']!=source_id: continue
        if opinion.get('withdrawn') or not opinion.get('carry_forward'): continue
        if context['strict'] and _date(opinion['available_at'])>boundary:
            excluded.append({'comment_id':opinion['comment_id'],'reason':'opinion_not_available_at_cutoff'})
            continue
        item=deepcopy(opinion)
        item.update(review_status='pending',review_required=True,epistemic_role='human_input_not_verified_fact')
        opinions.append(item)
    return {'reference':_reference(row),'content':_payload(row),'validation_status':row.get('validation_status'),
            'role':'draft_to_revise_not_evidence','opinions':opinions,'excluded_opinions':excluded}


def _bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _payload(row):
    # Deliberately no files or source-artifact paths are opened. Existing artifact
    # pointers remain metadata, not input for this module's filesystem access.
    keys = ("id", "company_id", "scope", "primary_document_id", "material_available_at",
            "knowledge_cutoff_at", "run_started_at", "created_at", "parent_snapshot_id",
            "baseline_snapshot_id", "title", "summary", "answer", "result", "human_notes",
            "inherited_comment_refs", "mode", "model", "source_refs", "researcher_id", "config_version")
    return {key: deepcopy(row[key]) for key in keys if key in row}


def _reference(row):
    return {"snapshot_id": row["id"], "revision_at_freeze": row["revision"],
            "researcher_id": row.get('researcher_id'),
            "company_id": row["company_id"], "scope": row["scope"],
            "primary_document_id": row["primary_document_id"],
            "material_available_at": row.get("material_available_at"),
            "knowledge_cutoff_at": row.get("knowledge_cutoff_at"),
            "run_started_at": row.get("run_started_at"),
            "payload_sha256": hashlib.sha256(_bytes(_payload(row))).hexdigest()}


def build_context(store: Store, company, scope, cutoff, strict=True, researcher_id=None, material=None, document_metadata=None, rerun_from=None):
    """Capture eligible annual baselines and a history directory, not all answers."""
    # The outer lock spans eligibility and payload capture. Store's nested shared
    # read lock is compatible, and its per-path thread lock is reentrant.
    with store._transaction() as state:
        context = store.context(company, scope, cutoff, strict=strict, researcher_id=researcher_id,
                                material=material,document_metadata=document_metadata)
        baseline_id = context["baseline_snapshot_id"]
        baseline = state["snapshots"].get(baseline_id) if baseline_id else None
        context.update(schema_version="1.2" if material is not None else "1.1", built_at=datetime.now(timezone.utc).isoformat(),
                       baseline=({"reference": _reference(baseline), **({"content": _payload(baseline)} if material is None else {})} if baseline else None),
                       baselines=[{"reference":_reference(state['snapshots'][key]),"content":_payload(state['snapshots'][key])} for key in context['baseline_snapshot_ids']] if material is not None else [],
                       document_metadata={key:{field:deepcopy(value[field]) for field in ('form','period_end','company_id') if field in value} for key,value in (document_metadata or {}).items()},
                       history_directory=[_reference(state["snapshots"][key]) for key in context["history_snapshot_ids"]],
                       baseline_policy="frozen_do_not_replace_during_run",
                       human_input_policy="pending_review_not_evidence",
                       token_budget=None, truncation="none",
                       integration_status="prepared_not_an_analysis_execution")
        if rerun_from:
            context['rerun_source'] = _rerun_feedback(state,context,rerun_from)
            context['rerun_feedback_policy'] = 'review_against_sources_never_blindly_obey'
        context["context_id"] = "context-" + hashlib.sha256(_bytes(context)).hexdigest()[:24]
        return context


def freeze_context(context, run_folder):
    """Exclusively publish context_manifest.json; refuse overwrites, even identical.

    A temporary fully fsynced file is hard-linked into place with exclusive-create
    semantics, so readers cannot observe partially written JSON.
    """
    if not context.get("context_id") or context.get("schema_version") not in {"1.1","1.2"}:
        raise ArchiveError("Build a versioned context before freezing")
    folder = Path(run_folder)
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / "context_manifest.json"
    descriptor, temporary = tempfile.mkstemp(prefix=".context-", dir=folder)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(_bytes(context))
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError as exc:
            raise ArchiveError("A frozen context already exists; use a new run folder") from exc
        directory = os.open(folder, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        os.unlink(temporary)
    return destination


def read_history(context, store: Store, snapshot_id):
    """Read an allowed historical payload if still eligible; never substitute one.

    Revision changes are warnings; removal from adoption or immutable payload
    changes are refusals. Neither outcome mutates the frozen manifest.
    """
    if not isinstance(snapshot_id, str):
        raise ArchiveError("History snapshot ID must be a string")
    entries = {row["snapshot_id"]: row for row in context.get("history_directory", [])}
    reference = entries.get(snapshot_id)
    if reference is None or snapshot_id not in context.get("history_snapshot_ids", []):
        raise ArchiveError("History snapshot is not in the frozen allowlist")
    with store._transaction() as state:
        row = state["snapshots"].get(snapshot_id)
        if row is None or row["status"] != "adopted":
            raise ArchiveError("History was withdrawn from adoption after freezing; access refused")
        if (row["company_id"], row["scope"], row.get('researcher_id')) != (context["company_id"], context["scope"], context.get('researcher_id')):
            raise ArchiveError("History does not belong to the frozen company and research scope")
        current = store.context(context["company_id"], context["scope"], context["cutoff"], strict=context["strict"], researcher_id=context.get('researcher_id'),
                                material=context.get('current_material'),document_metadata=context.get('document_metadata'))
        eligible = set(current["history_snapshot_ids"])
        eligible.update(current['baseline_snapshot_ids'])
        if snapshot_id not in eligible:
            raise ArchiveError("History no longer meets the frozen time boundary")
        payload = _payload(row)
        if hashlib.sha256(_bytes(payload)).hexdigest() != reference["payload_sha256"]:
            raise ArchiveError("Historical content differs from its frozen identity")
        warnings = []
        if row["revision"] != reference["revision_at_freeze"]:
            warnings.append("Archive state or human opinions changed after context freeze; review required")
        if row.get("inheritance_review_required"):
            warnings.append("Inherited input has a withdrawal or revision notice; review required")
        return {"snapshot_id": snapshot_id, "content": payload, "reference": deepcopy(reference),
                "warnings": warnings, "inheritance_notices": deepcopy(row.get("inheritance_notices", [])),
                "status": "loaded_with_warning" if warnings else "loaded",
                "context_id": context["context_id"]}
