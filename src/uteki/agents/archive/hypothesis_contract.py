"""Explicit identities for annual hypotheses and quarterly revision proposals.

Pure contract validation only. No persistence, adoption, evidence verification or
model call occurs here. The archive must check its current revision atomically.
"""
from __future__ import annotations
from datetime import date
from hashlib import sha256
import json
from typing import Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class EvidenceRef(Contract):
    document_id: str = Field(min_length=1)
    index_id: str = Field(min_length=1)
    block_id: str = Field(min_length=1)
    source_available_on: date


class Hypothesis(Contract):
    hypothesis_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    statement: str = Field(min_length=1)
    business_scope: str = Field(min_length=1)
    horizon: str = Field(min_length=1)
    conditions: tuple[str, ...]
    observations: tuple[str, ...]
    reconsider_when: str = Field(min_length=1)
    support: tuple[EvidenceRef, ...]
    opposition: tuple[EvidenceRef, ...]
    status: Literal['active', 'withdrawn'] = 'active'


class AnnualRevision(Contract):
    schema_version: Literal['1.0'] = '1.0'
    report_id: str
    revision_id: str
    company_id: str
    researcher_id: str
    scope: str
    primary_document_id: str
    cutoff: date
    parent_revision_id: str | None
    hypotheses: tuple[Hypothesis, ...]
    actor: str
    based_on_validation_ids: tuple[str, ...] = ()

    @model_validator(mode='after')
    def unique_and_time_bounded(self):
        ids = [h.hypothesis_id for h in self.hypotheses]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate hypothesis identity')
        if any(e.source_available_on > self.cutoff for h in self.hypotheses for e in h.support+h.opposition):
            raise ValueError('Evidence newer than revision cutoff')
        return self


class Assessment(Contract):
    hypothesis_id: str
    hypothesis_revision: int = Field(ge=1)
    verdict: Literal['supported', 'weakened', 'refuted', 'insufficient', 'mixed']
    explanation: str = Field(min_length=1)
    evidence: tuple[EvidenceRef, ...]

    @model_validator(mode='after')
    def needs_evidence(self):
        if self.verdict != 'insufficient' and not self.evidence:
            raise ValueError('A directional verdict requires evidence')
        return self


class ValidationRecord(Contract):
    validation_id: str
    report_id: str
    baseline_revision_id: str
    researcher_id: str
    cutoff: date
    assessments: tuple[Assessment, ...]
    prior_validation_ids: tuple[str, ...] = ()


class Change(Contract):
    action: Literal['add', 'replace', 'withdraw']
    hypothesis_id: str
    expected_hypothesis_revision: int | None
    replacement: Hypothesis | None
    reason: str = Field(min_length=1)
    validation_ids: tuple[str, ...]


class RevisionProposal(Contract):
    proposal_id: str
    report_id: str
    baseline_revision_id: str
    researcher_id: str
    cutoff: date
    changes: tuple[Change, ...] = Field(min_length=1)


def new_identity(prefix):
    # Identity is not regenerated from editable wording.
    return prefix + '-' + uuid4().hex


def revision_identity(payload):
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)
    return 'revision-' + sha256(encoded.encode()).hexdigest()[:24]


def check_validation(baseline: AnnualRevision, record: ValidationRecord):
    if (record.report_id,record.baseline_revision_id,record.researcher_id) != (
            baseline.report_id,baseline.revision_id,baseline.researcher_id):
        raise ValueError('Validation targets another report, researcher or revision')
    if record.cutoff < baseline.cutoff:
        raise ValueError('Validation precedes its baseline')
    targets = {h.hypothesis_id:h for h in baseline.hypotheses}
    seen = set()
    for assessment in record.assessments:
        target = targets.get(assessment.hypothesis_id)
        if not target or target.revision != assessment.hypothesis_revision or target.status != 'active':
            raise ValueError('Unknown, stale or withdrawn hypothesis')
        if target.hypothesis_id in seen:
            raise ValueError('Duplicate assessment')
        seen.add(target.hypothesis_id)
        if any(e.source_available_on > record.cutoff for e in assessment.evidence):
            raise ValueError('Validation evidence after cutoff')
    # Missing assessments intentionally have no effect; silence is not support.


def preview_revision(baseline: AnnualRevision, proposal: RevisionProposal,
                     records: tuple[ValidationRecord, ...], *, actor: str) -> AnnualRevision:
    """Compute candidate diff result, not adopt it or authorize the actor."""
    if not actor.strip():
        raise ValueError('Explicit revision author required')
    if (proposal.report_id,proposal.baseline_revision_id,proposal.researcher_id) != (
            baseline.report_id,baseline.revision_id,baseline.researcher_id):
        raise ValueError('Stale baseline or another researcher')
    if proposal.cutoff < baseline.cutoff:
        raise ValueError('Cannot move revision cutoff backwards')
    lookup = {r.validation_id:r for r in records}
    if len(lookup) != len(records):
        raise ValueError('Duplicate validation identity')
    hypotheses = {h.hypothesis_id:h for h in baseline.hypotheses}
    changed, used = set(), set()
    for change in proposal.changes:
        if change.hypothesis_id in changed:
            raise ValueError('One operation per hypothesis per proposal')
        changed.add(change.hypothesis_id)
        for validation_id in change.validation_ids:
            record = lookup.get(validation_id)
            if not record:
                raise ValueError('Missing cited validation')
            check_validation(baseline, record)
            if record.cutoff > proposal.cutoff:
                raise ValueError('Cited validation is newer than proposal')
            if change.action != 'add' and not any(a.hypothesis_id == change.hypothesis_id for a in record.assessments):
                raise ValueError('Cited validation does not assess this hypothesis')
            used.add(validation_id)
        previous = hypotheses.get(change.hypothesis_id)
        if change.action == 'add':
            if previous or change.expected_hypothesis_revision is not None:
                raise ValueError('New hypothesis already exists')
            expected = 1
        else:
            if not previous or previous.revision != change.expected_hypothesis_revision:
                raise ValueError('Hypothesis revision conflict')
            expected = previous.revision+1
        if change.action == 'withdraw':
            if change.replacement is not None or previous.status == 'withdrawn':
                raise ValueError('Invalid withdrawal')
            hypotheses[change.hypothesis_id] = previous.model_copy(update=dict(revision=expected,status='withdrawn'))
        else:
            replacement = change.replacement
            if not replacement or replacement.hypothesis_id != change.hypothesis_id or replacement.revision != expected:
                raise ValueError('Replacement must preserve identity and increment revision')
            hypotheses[change.hypothesis_id] = replacement
    payload = baseline.model_dump(exclude={'revision_id'})
    payload.update(parent_revision_id=baseline.revision_id,cutoff=proposal.cutoff,
                   hypotheses=tuple(h.model_dump() for h in hypotheses.values()), actor=actor,
                   based_on_validation_ids=tuple(sorted(used)))
    return AnnualRevision.model_validate(dict(**payload,revision_id=revision_identity(payload)))
