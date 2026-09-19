"""File-backed research snapshots, explicit adoption and bounded context eligibility.

The state and audit trail are committed as one JSON document. Model artifacts are
never rewritten; editable text is always a new candidate snapshot.
"""
from __future__ import annotations
from .review_blocks import review_blocks, valid_decisions

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
from uuid import uuid4


class ArchiveError(ValueError):
    """Invalid transition, missing input, or unresolved validation."""


class ConflictError(ArchiveError):
    """The supplied revision or adoption slot is no longer current."""


_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _date(value: str) -> datetime:
    if not value:
        raise ArchiveError("A verified availability timestamp is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ArchiveError("Invalid timestamp") from exc
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _slot(row: dict) -> tuple:
    return row["company_id"], row.get("researcher_id", "unassigned"), row["scope"], row["primary_document_id"]


def _slot_revision(state, row):
    # A token over the complete slot detects even adopt/archive/replace cycles.
    values = sorted((r['id'], r['revision'], r['status']) for r in state['snapshots'].values() if _slot(r) == _slot(row))
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        with _LOCKS_GUARD:
            self._lock = _LOCKS.setdefault(str(self.path), threading.RLock())

    @contextmanager
    def _transaction(self, write=False):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self.path.with_suffix(self.path.suffix + ".lock").open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX if write else fcntl.LOCK_SH)
            try:
                if self.path.exists():
                    state = json.loads(self.path.read_text(encoding="utf-8"))
                else:
                    state = {"schema_version": "1.0", "snapshots": {}, "comments": {}, "audit_events": []}
                yield state
                if write:
                    self._save(state)
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _save(self, state):
        data = json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        descriptor, temporary = tempfile.mkstemp(prefix=self.path.name + ".", dir=self.path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
            directory = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _view(state, row):
        result = deepcopy(row)
        result['slot_revision'] = _slot_revision(state, row)
        result['audit_events'] = [deepcopy(event) for event in state['audit_events']
                                  if not event.get('action', '').startswith('annotation_') and
                                  (row['id'] in (event.get('snapshot_id'), event.get('result_snapshot_id'))
                                  or row['id'] in event.get('changed_snapshot_ids', [])
                                  or row['id'] in event.get('snapshot_ids', []))]
        lineage, seen, current = [], set(), row
        while current and current['id'] not in seen:
            seen.add(current['id'])
            lineage.append({key: deepcopy(current.get(key)) for key in (
                'id', 'parent_snapshot_id', 'created_at', 'edited_at', 'author',
                'editor_type', 'edit_kind', 'edit_reason', 'agent_provenance', 'status', 'title')})
            current = state['snapshots'].get(current.get('parent_snapshot_id'))
        result['revision_lineage'] = lineage
        result["comments"] = [deepcopy(versions[-1]) for versions in state["comments"].values()
                              if versions[-1]["snapshot_id"] == row["id"]]
        return result

    @staticmethod
    def _sort(row):
        # Group by primary material first; versions then sort by execution time.
        def instant(value):
            try:
                return _date(value).timestamp()
            except ArchiveError:
                return float("-inf")
        return (instant(row.get("material_available_at")), row["primary_document_id"],
                instant(row.get("created_at") or row.get("run_started_at")), row["id"])

    def list(self, company=None, scope=None, researcher_id=None):
        with self._transaction() as state:
            rows = [self._view(state, row) for row in state["snapshots"].values()
                    if (company is None or row["company_id"] == company)
                    and (scope is None or row["scope"] == scope)
                    and (researcher_id is None or row.get('researcher_id') == researcher_id)]
            return sorted(rows, key=self._sort, reverse=True)

    def migrate_researchers(self, identities, dry_run=True):
        """Explicit id mapping from verified imports; no guessing a team from mode.

        Preserve source artifacts, content and user decisions. A byte-exact backup
        is written before committing the one-time migration, under the same lock.
        """
        with self._transaction() as state:
            if state.get('schema_version') == '1.1':
                return {'changed': [], 'already_migrated': True}
            proposed = deepcopy(state)
            changes = []
            def identity(row, seen=None):
                seen = set() if seen is None else seen
                if row['id'] in seen:
                    raise ArchiveError('Cyclic revision lineage')
                seen.add(row['id'])
                if row.get('researcher_id') and row['researcher_id'] != 'unassigned':
                    return {k: row[k] for k in ('researcher_id', 'researcher_label', 'config_version') if k in row}
                if row['id'] in identities:
                    return identities[row['id']]
                parent = proposed['snapshots'].get(row.get('parent_snapshot_id'))
                return identity(parent, seen) if parent else {'researcher_id': 'unassigned', 'researcher_label': '待归类 / Unassigned'}
            for row in proposed['snapshots'].values():
                fields = identity(row)
                row.update(fields)
                changes.append({'snapshot_id': row['id'], **fields})
            occupied = set()
            for row in proposed['snapshots'].values():
                if row['status'] == 'adopted':
                    if _slot(row) in occupied:
                        raise ConflictError('Migration found duplicate effective reports')
                    occupied.add(_slot(row))
            report = {'changed': changes, 'already_migrated': False}
            if dry_run:
                return report
            # Upgrade to exclusive lock before saving and fail if the source changed.
            before = self.path.read_bytes() if self.path.exists() else None
        with self._lock, self.path.with_suffix(self.path.suffix + '.lock').open('a+') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if (self.path.read_bytes() if self.path.exists() else None) != before:
                raise ConflictError('Archive changed during migration; retry')
            backup = None
            if before is not None:
                backup = self.path.with_name(self.path.name + '.pre-v1.1-' + hashlib.sha256(before).hexdigest()[:12] + '.bak')
                if not backup.exists():
                    with backup.open('xb') as output:
                        output.write(before); output.flush(); os.fsync(output.fileno())
                elif backup.read_bytes() != before:
                    raise ArchiveError('Migration backup differs')
            proposed['schema_version'] = '1.1'
            proposed['audit_events'].append({'event_id': uuid4().hex, 'action': 'migrate_researchers',
                'at': _now(), 'actor': 'migration', 'mapping': changes, 'backup': str(backup) if backup else None})
            self._save(proposed)
            return {**report, 'backup': str(backup) if backup else None}

    def annotations(self, snapshot_id):
        with self._transaction() as state:
            if snapshot_id not in state['snapshots']:
                raise ArchiveError('Snapshot not found')
            collection = state.get('reading_annotations', {}).get(snapshot_id, {'revision': 0, 'marks': []})
            return self._annotation_view(state, collection)

    @staticmethod
    def _annotation_view(state, collection):
        marks = [deepcopy(m) for m in collection['marks'] if not m.get('removed_at')]
        for mark in marks:
            versions = state['comments'].get(mark.get('comment_id'), [])
            if versions:
                opinion = versions[-1]
                mark.update(note=opinion['text'], carry_forward=opinion['carry_forward'],
                            note_withdrawn=opinion['withdrawn'], note_version=opinion['version'])
        return {'revision': collection['revision'], 'marks': marks}

    def annotate(self, snapshot_id, action, expected_revision, **data):
        """Atomic anchored notes; legacy bare underlines remain reading-only."""
        with self._transaction(write=True) as state:
            row = state['snapshots'].get(snapshot_id)
            if row is None or row['status'] == 'deleted':
                raise ArchiveError('Snapshot unavailable for annotation')
            collection = state.setdefault('reading_annotations', {}).setdefault(snapshot_id, {'revision': 0, 'marks': []})
            if type(expected_revision) is not int or expected_revision != collection['revision']:
                raise ConflictError('Annotations changed; reload before saving')
            timestamp = _now()
            if action == 'add':
                number, start, end = data.get('claim_number'), data.get('start'), data.get('end')
                claims = row.get('answer', {}).get('claims', []) if isinstance(row.get('answer'), dict) else []
                if type(number) is not int or not 1 <= number <= len(claims):
                    raise ArchiveError('Invalid claim')
                claim = claims[number - 1]
                text = claim.get('text', '') if isinstance(claim, dict) else str(claim)
                text_hash = hashlib.sha256(text.encode()).hexdigest()
                if data.get('text_hash') != text_hash:
                    raise ArchiveError('Claim text changed; reload before annotating')
                if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text)
                        or end - start > 12000 or not text[start:end].strip() or data.get('quote') != text[start:end]):
                    raise ArchiveError('Selected text does not match the claim')
                active = [m for m in collection['marks'] if not m.get('removed_at')]
                if len(active) >= 500:
                    raise ArchiveError('Too many annotations in this snapshot')
                for mark in active:
                    if mark['claim_number'] == number and start < mark['end'] and end > mark['start']:
                        raise ArchiveError('Selection overlaps an existing annotation; remove it first')
                mark = {'annotation_id': uuid4().hex, 'claim_number': number, 'start': start, 'end': end,
                        'quote': text[start:end], 'text_hash': text_hash, 'created_at': timestamp, 'actor': 'user'}
                collection['marks'].append(mark)
            elif action in {'remove', 'note'}:
                mark = next((m for m in collection['marks'] if m['annotation_id'] == data.get('annotation_id') and not m.get('removed_at')), None)
                if mark is None:
                    raise ArchiveError('Annotation not found')
                if action == 'remove':
                    mark['removed_at'] = timestamp
            else:
                raise ArchiveError('Unknown annotation action')
            if action == 'note' or (action == 'add' and 'note' in data) or (action == 'remove' and mark.get('comment_id')):
                versions = state['comments'].get(mark.get('comment_id'), [])
                previous = versions[-1] if versions else {}
                if action != 'add' and data.get('expected_note_version', 0) != previous.get('version', 0):
                    raise ConflictError('Review note changed; reload before saving')
                note = data.get('note', previous.get('text', ''))
                if not isinstance(note, str) or not note.strip() or len(note) > 12000:
                    raise ArchiveError('A review note of 1–12000 characters is required')
                comment_id = mark.get('comment_id') or uuid4().hex
                opinion = dict(previous)
                opinion.update(comment_id=comment_id, snapshot_id=snapshot_id,
                    version=len(versions)+1, created_at=previous.get('created_at', timestamp),
                    available_at=timestamp, author='user', text=note.strip(),
                    kind=previous.get('kind','unclassified'), review_status='pending', withdrawn=action=='remove',
                    carry_forward=action!='remove' and bool(data.get('carry_forward', previous.get('carry_forward', True))),
                    source_selection={key:deepcopy(mark[key]) for key in ('annotation_id','claim_number','start','end','quote','text_hash')})
                mark['comment_id'] = comment_id
                state['comments'][comment_id] = [*versions, opinion]
                row['revision'] += 1
                row['updated_at'] = timestamp
                if previous:
                    def touch(target):
                        target['revision'] += 1
                        target['updated_at'] = timestamp
                    self._flag_descendants(state, snapshot_id, timestamp, touch, comment_id)
            collection['revision'] += 1
            state['audit_events'].append({'event_id': uuid4().hex, 'action': 'annotation_' + action,
                                         'snapshot_id': snapshot_id, 'annotation_id': mark['annotation_id'],
                                         'at': timestamp, 'actor': 'user'})
            return self._annotation_view(state, collection)

    def seed(self, rows):
        """Explicit, idempotent import. Existing IDs are never overwritten."""
        with self._transaction(write=True) as state:
            added = []
            for source in rows:
                row = deepcopy(source)
                for key in ("id", "company_id", "scope", "primary_document_id"):
                    if not row.get(key):
                        raise ArchiveError(f"Missing snapshot field: {key}")
                if row["id"] in state["snapshots"]:
                    continue
                if row.get("status", "candidate") != "candidate":
                    raise ArchiveError("Imported results must start as candidates")
                row.pop("comments", None)
                row.update(status="candidate", revision=1)
                row.setdefault("validation_status", "pending")
                row.setdefault("created_at", row.get("run_started_at") or _now())
                row.setdefault("updated_at", row["created_at"])
                row.setdefault("inherited_comment_refs", [])
                row.setdefault('researcher_id', 'unassigned')
                state["snapshots"][row["id"]] = row
                added.append(row["id"])
            if added:
                state["audit_events"].append({"event_id": uuid4().hex, "action": "seed",
                                               "snapshot_ids": added, "at": _now(), "actor": "importer"})
            return [self._view(state, row) for row in sorted(state["snapshots"].values(), key=self._sort, reverse=True)]

    def record_agent_revision(self, snapshot_id, expected_revision, *, answer, reason,
                              agent_id, model, run_id, artifact_path, artifact_sha256,
                              citation_errors=None):
        """Trusted local agent handoff; deliberately unavailable over the human API.

        A new candidate is saved even when its source changed during execution,
        via an explicit conflict/retry, never an implicit overwrite or adoption.
        """
        provenance = dict(agent_id=agent_id, model=model, run_id=run_id,
                          artifact_path=str(artifact_path), artifact_sha256=artifact_sha256)
        if any(not isinstance(v, str) or not v.strip() for v in provenance.values()):
            raise ArchiveError('Agent identity, model, run and artifact are required')
        artifact = Path(artifact_path)
        if not artifact.is_file() or hashlib.sha256(artifact.read_bytes()).hexdigest() != artifact_sha256:
            raise ArchiveError('Agent artifact is missing or changed')
        if not isinstance(reason, str) or not reason.strip():
            raise ArchiveError('Agent revision reason is required')
        if not isinstance(answer, dict) or not answer:
            raise ArchiveError('Agent answer must be a nonempty object')
        if citation_errors is not None and not isinstance(citation_errors, list):
            raise ArchiveError('Citation errors must be a list')
        return self.act(snapshot_id, 'agent_edit', expected_revision, answer=answer,
                        reason=reason, actor=agent_id, agent_provenance=provenance,
                        citation_errors=deepcopy(citation_errors or []))

    def act(self, snapshot_id, action, expected_revision, **kwargs):
        action = {"comment": "add_comment", "withdraw_opinion": "withdraw_comment"}.get(action, action)
        with self._transaction(write=True) as state:
            row = state["snapshots"].get(snapshot_id)
            if row is None:
                raise ArchiveError("Snapshot not found")
            if type(expected_revision) is not int or expected_revision != row["revision"]:
                raise ConflictError("Snapshot changed; reload before making this decision")
            before = deepcopy(row)
            previous_states = {key: {"status": item["status"], "revision": item["revision"]}
                               for key, item in state["snapshots"].items()}
            timestamp = _now()
            changed = []
            result_row = row

            def touch(target):
                if target["id"] not in changed:
                    target["revision"] += 1
                    target["updated_at"] = timestamp
                    changed.append(target["id"])

            structural_action = action if action in {'insert_block','delete_block'} else None
            if structural_action:
                answer=deepcopy(row.get('answer'))
                if not isinstance(answer,dict): raise ArchiveError('Unsupported report format')
                index=kwargs.get('block_index')
                if type(index) is not int: raise ArchiveError('Invalid block position')
                markdown='report_markdown' in answer
                items=answer['report_markdown'].splitlines() if markdown else answer.get('claims',[])
                if not 0 <= index <= len(items): raise ArchiveError('Invalid block position')
                if structural_action=='insert_block':
                    kind=kwargs.get('block_kind');text=kwargs.get('text')
                    labels={'fact':'事实','inference':'推断','hypothesis':'假设','question':'待验证问题'}
                    if kind not in labels or not isinstance(text,str) or not text.strip() or len(text)>20000:
                        raise ArchiveError('Choose a block type and enter text')
                    if markdown:
                        items[index:index]=['',labels[kind]+'：'+text.strip().replace('\n',' '),'']
                    else: items.insert(index,{'kind':kind,'text':text.strip(),'citations':[]})
                else:
                    count=kwargs.get('block_count',1)
                    if type(count) is not int or count<1 or index+count>len(items) or (not markdown and count!=1):
                        raise ArchiveError('Invalid deletion range')
                    del items[index:index+count]
                if markdown:answer['report_markdown']='\n'.join(items)
                else:answer['claims']=items
                if len(str(answer))>90000:raise ArchiveError('Report too large')
                kwargs['answer']=answer
                kwargs['human_notes']=kwargs.get('human_notes') or ('新增内容块' if structural_action=='insert_block' else '删除内容块')
                action='edit'

            if action in {'accept_block', 'unaccept_block'}:
                if row.get('status') == 'deleted':
                    raise ArchiveError('Restore the report before reviewing blocks')
                blocks=review_blocks(row.get('answer'))
                key=kwargs.get('block_id')
                if key not in blocks or kwargs.get('block_hash') != blocks[key]:
                    raise ConflictError('Block changed; reload before reviewing')
                decisions=valid_decisions(row)
                decision={'hash':blocks[key], 'accepted':action=='accept_block', 'at':timestamp,
                          'actor':kwargs.get('actor','user'), 'source_snapshot_id':snapshot_id}
                decisions[key]=decision
                row['block_decisions']=decisions
                row.setdefault('block_review_events',[]).append(dict(decision,block_id=key))
            elif action == "adopt":
                if row.get('researcher_id', 'unassigned') == 'unassigned':
                    raise ArchiveError('Assign a verified researcher before adoption')
                if kwargs.get('expected_slot_revision') is not None and kwargs['expected_slot_revision'] != _slot_revision(state, row):
                    raise ConflictError('Report slot changed; reload before replacing')
                if row["status"] not in {"candidate", "archived"}:
                    raise ArchiveError("Only candidate or archived results can be adopted")
                if row.get("validation_status") != "passed":
                    raise ArchiveError("Evidence validation must pass before adoption")
                if row.get("primary_inferred") and kwargs.get("confirm_primary") is not True:
                    raise ArchiveError("Explicitly confirm the inferred primary material before adoption")
                for name in ("material_available_at", "knowledge_cutoff_at", "run_started_at"):
                    _date(row.get(name))
                if _date(row["knowledge_cutoff_at"]) < _date(row["material_available_at"]):
                    raise ArchiveError("Knowledge cutoff cannot precede the primary material")
                peers = [other for other in state["snapshots"].values()
                         if other["id"] != row["id"] and _slot(other) == _slot(row)]
                current = next((other for other in peers if other['status'] == 'adopted'), None)
                if current:
                    if (kwargs.get('replace_snapshot_id') != current['id']
                            or type(kwargs.get('replace_revision')) is not int
                            or kwargs['replace_revision'] != current['revision']
                            or kwargs.get('expected_slot_revision') != _slot_revision(state, row)):
                        raise ConflictError('Explicitly confirm the current version and slot before replacement')
                    current['status'] = 'archived'
                    current['replaced_by_snapshot_id'] = row['id']
                    touch(current)
                    self._flag_descendants(state, current['id'], timestamp, touch)
                row["status"] = "adopted"
                row["adopted_at"] = timestamp
                if row.get("primary_inferred"):
                    row["primary_confirmed_at"] = timestamp
                    row["primary_confirmed_by"] = kwargs.get("actor", "user")
            elif action == 'reject':
                if row['status'] != 'candidate':
                    raise ArchiveError('Only candidates can be rejected')
                if not isinstance(kwargs.get('reason'), str) or not kwargs['reason'].strip():
                    raise ArchiveError('A rejection reason is required')
                row['status'] = 'rejected'
            elif action == 'reconsider':
                if row['status'] != 'rejected':
                    raise ArchiveError('Only rejected results can be reconsidered')
                row['status'] = 'candidate'
            elif action == "review":
                if row["status"] not in {"candidate", "archived"} or row.get("edit_kind") not in {"human_revision", "agent_revision"}:
                    raise ArchiveError("Only a revision can receive explicit human review")
                notes = kwargs.get("review_notes", kwargs.get("reason", ""))
                if not isinstance(notes, str) or not notes.strip():
                    raise ArchiveError("Human verification notes are required")
                parent = state["snapshots"].get(row.get("parent_snapshot_id"), {})
                if row.get("citation_errors") or parent.get("validation_status") != "passed":
                    raise ArchiveError("Unresolved source validation requires an evidence repair run, not a review override")
                row.update(validation_status="passed", review_method="human", review_notes=notes,
                           reviewed_at=timestamp, reviewed_by=kwargs.get("actor", "user"))
            elif action == "archive":
                if row["status"] not in {"candidate", "adopted"}:
                    raise ArchiveError("Only candidates or adopted results can be archived")
                row["status"] = "archived"
                self._flag_descendants(state, snapshot_id, timestamp, touch)
            elif action == "delete":
                if row["status"] not in {"candidate", "archived", "rejected"}:
                    raise ArchiveError("Archive an adopted result before deleting it")
                row["status"] = "deleted"
                self._flag_descendants(state, snapshot_id, timestamp, touch)
            elif action == "restore":
                if row["status"] != "deleted":
                    raise ArchiveError("Only deleted results can be restored")
                row["status"] = "archived"
            elif action in {"edit", "agent_edit"}:
                agent_edit = action == 'agent_edit'
                if agent_edit and not kwargs.get('agent_provenance'):
                    raise ArchiveError('Agent provenance required')
                if row["status"] not in {"candidate", "archived", "adopted", "rejected"}:
                    raise ArchiveError("Deleted results cannot be edited")
                updates = deepcopy(kwargs.get("updates", {}))
                for name in ("answer", "result", "title", "summary", "human_notes"):
                    if name in kwargs:
                        updates[name] = deepcopy(kwargs[name])
                if not updates or set(updates) - {"answer", "result", "title", "summary", "human_notes"}:
                    raise ArchiveError("Provide editable answer fields only")
                if not agent_edit and not structural_action and 'answer' in updates and isinstance(row.get('answer'), dict):
                    old, new = row['answer'], updates['answer']
                    if not isinstance(new, dict) or set(new) != set(old):
                        raise ArchiveError('Preserve the answer schema and evidence')
                    if len(new.get('claims', [])) != len(old.get('claims', [])):
                        raise ArchiveError('This revision editor preserves claim and citation identities')
                    for a, b in zip(old.get('claims', []), new.get('claims', [])):
                        if not isinstance(b, dict) or {k:v for k,v in a.items() if k != 'text'} != {k:v for k,v in b.items() if k != 'text'}:
                            raise ArchiveError('Citations cannot be changed through text editing')
                        if not isinstance(b.get('text'), str) or not b['text'].strip() or len(b['text']) > 20000:
                            raise ArchiveError('Invalid claim text')
                    for key in new:
                        if key == 'report_markdown':
                            if not isinstance(new[key], str) or not new[key].strip() or len(new[key]) > 60000:
                                raise ArchiveError('Report must contain 1–60000 characters')
                        elif key in {'limitations', 'findings'}:
                            if not isinstance(new[key], list) or any(not isinstance(v, str) or len(v)>20000 for v in new[key]):
                                raise ArchiveError('Invalid answer list')
                        elif key != 'claims' and new[key] != old[key]:
                            raise ArchiveError('Only claims, limitations and findings may be edited')
                result_row = deepcopy(row)
                result_row.update(updates)
                result_row.update(id=f"{snapshot_id}-r-{uuid4().hex[:12]}", parent_snapshot_id=snapshot_id,
                                  status="candidate", validation_status="pending", revision=1,
                                  created_at=timestamp, updated_at=timestamp, edited_at=timestamp,
                                  author=kwargs.get("actor", "user"),
                                  editor_type='agent' if agent_edit else 'human',
                                  edit_kind='agent_revision' if agent_edit else 'human_revision',
                                  edit_reason=kwargs.get('reason') or updates.get('human_notes', ''),
                                  available_at=timestamp)
                result_row['block_decisions'] = valid_decisions(result_row)
                if structural_action:
                    old_blocks=review_blocks(row.get('answer'));new_blocks=review_blocks(result_row.get('answer'))
                    carried={}
                    for old_key,decision in valid_decisions(row).items():
                        digest=old_blocks[old_key]
                        matches=[key for key,value in new_blocks.items() if value==digest]
                        if len(matches)==1 and list(old_blocks.values()).count(digest)==1:
                            carried[matches[0]]=deepcopy(decision)
                    result_row['block_decisions']=carried
                    result_row['structure_change']={'action':structural_action,'index':kwargs['block_index'],
                                                   'count':kwargs.get('block_count',1),'kind':kwargs.get('block_kind')}

                result_row.pop('agent_provenance', None)
                if agent_edit:
                    result_row['agent_provenance'] = deepcopy(kwargs['agent_provenance'])
                    result_row['citation_errors'] = deepcopy(kwargs.get('citation_errors', []))
                    result_row.pop('human_notes', None)
                result_row['edit_diff'] = {key: {'before': deepcopy(row.get(key)), 'after': deepcopy(value)} for key, value in updates.items() if row.get(key) != value}
                if not result_row['edit_diff']:
                    raise ArchiveError('No changes to save')
                result_row['inherited_comment_refs'] = []
                for key in ('review_method', 'review_notes', 'reviewed_at', 'reviewed_by', 'replaced_by_snapshot_id'):
                    result_row.pop(key, None)
                result_row.pop("adopted_at", None)
                state["snapshots"][result_row["id"]] = result_row
                changed.append(result_row["id"])
            elif action in {"add_comment", "edit_comment", "withdraw_comment"}:
                if row["status"] == "deleted":
                    raise ArchiveError("Restore the result before changing opinions")
                comment_id = kwargs.get("comment_id") or kwargs.get("opinion_id")
                if action == "add_comment":
                    comment = {"comment_id": uuid4().hex, "snapshot_id": snapshot_id, "version": 1,
                               "created_at": timestamp, "withdrawn": False}
                    versions = []
                else:
                    versions = state["comments"].get(comment_id)
                    if not versions or versions[-1]["snapshot_id"] != snapshot_id:
                        raise ArchiveError("Opinion does not belong to this snapshot")
                    comment = deepcopy(versions[-1])
                    comment["version"] += 1
                if action == "withdraw_comment":
                    comment.update(withdrawn=True, carry_forward=False)
                else:
                    text = kwargs.get("text", comment.get("text", ""))
                    if not isinstance(text, str) or not text.strip():
                        raise ArchiveError("Opinion text cannot be empty")
                    kind = kwargs.get("kind", comment.get("kind", "unclassified"))
                    if kind not in {"preference", "fact_claim", "hypothesis", "unclassified"}:
                        raise ArchiveError("Unknown opinion kind")
                    comment.update(text=text, kind=kind, carry_forward=bool(kwargs.get("carry_forward", comment.get("carry_forward", False))))
                if action == 'add_comment' and kwargs.get('feedback_vote') is not None:
                    vote=kwargs['feedback_vote'];key=kwargs.get('block_id')
                    blocks=review_blocks(row.get('answer'))
                    if vote not in {'up','down'}:
                        raise ArchiveError('Unknown feedback vote')
                    if key not in blocks or kwargs.get('block_hash') != blocks[key]:
                        raise ConflictError('Feedback block changed; reload')
                    if len(text)>12000:
                        raise ArchiveError('Feedback too long')
                    comment.update(feedback_vote=vote,block_id=key,block_hash=blocks[key],
                                   source_answer=deepcopy(row.get('answer')),researcher_id=row.get('researcher_id'),
                                   policy_status='feedback_not_adopted_rule')
                comment.update(available_at=timestamp, author=kwargs.get("actor", "user"), review_status="pending")
                versions.append(comment)
                state["comments"][comment["comment_id"]] = versions
                if action != "add_comment":
                    self._flag_descendants(state, snapshot_id, timestamp, touch, comment["comment_id"])
            else:
                raise ArchiveError("Unknown archive action")

            # Editing creates a new revision without changing the original answer;
            # a revision tick on the parent prevents concurrent stale edits.
            touch(row)
            event = {"event_id": uuid4().hex, "action": action, "snapshot_id": snapshot_id,
                     "result_snapshot_id": result_row["id"], "at": timestamp,
                     "actor": kwargs.get("actor", "user"), "reason": kwargs.get("reason") or kwargs.get("human_notes", ""),
                     "before_status": before["status"], "after_status": row["status"],
                     "before_revision": before["revision"], "after_revision": row["revision"],
                     "changed_snapshot_ids": changed,
                     "block_id": kwargs.get("block_id"), "block_hash": kwargs.get("block_hash"),
                     "changes": [{"snapshot_id": key, "before": previous_states.get(key),
                                  "after": {"status": state["snapshots"][key]["status"],
                                            "revision": state["snapshots"][key]["revision"]}} for key in changed]}
            state["audit_events"].append(event)
            return {"snapshot": self._view(state, result_row), "revision": result_row["revision"],
                    "changed": [self._view(state, state["snapshots"][key]) for key in changed], "audit_event": event}

    @staticmethod
    def _flag_descendants(state, source_id, timestamp, touch, comment_id=None):
        affected = {source_id}
        while True:
            newly = {row["id"] for row in state["snapshots"].values()
                     if row.get("baseline_snapshot_id") in affected or row.get("parent_snapshot_id") in affected
                     or affected.intersection(row.get("baseline_snapshot_ids", []))}
            if newly <= affected:
                break
            affected |= newly
        for row in state["snapshots"].values():
            refs = row.get("inherited_comment_refs", [])
            carries = comment_id and any(ref.get("comment_id") == comment_id for ref in refs)
            if row["id"] != source_id and (row["id"] in affected or carries):
                row["inheritance_review_required"] = True
                notice = {"source_snapshot_id": source_id, "comment_id": comment_id, "at": timestamp}
                row.setdefault("inheritance_notices", []).append(notice)
                touch(row)

    def context(self, company, scope, cutoff, strict=True, researcher_id=None, material=None, document_metadata=None):
        """Return a manifest, never an implicit concatenation of all histories.

        strict=True also excludes analyses/opinions authored after the historical
        cutoff. Non-strict mode permits today's interpretation of older material,
        but material knowledge cutoffs always apply.
        """
        boundary = _date(cutoff)
        if material is not None:
            published = material.get('published_at') or material.get('filed_at')
            if not published or _date(published) > boundary:
                raise ArchiveError('Current material publication must be known and on/before cutoff')
        with self._transaction() as state:
            researchers = {r.get('researcher_id', 'unassigned') for r in state['snapshots'].values()
                           if (r['company_id'], r['scope']) == (company, scope)} - {'unassigned'}
            if researcher_id is None:
                if len(researchers) != 1:
                    raise ArchiveError('Select one researcher for context')
                researcher_id = next(iter(researchers))
            if researcher_id == 'unassigned':
                raise ArchiveError('Unassigned research cannot enter context')
            eligible, exclusions = [], []
            for row in state["snapshots"].values():
                if (row["company_id"], row["scope"]) != (company, scope):
                    continue
                reason = None
                if row.get('researcher_id') != researcher_id:
                    reason = 'outside_researcher'
                elif row["status"] != "adopted":
                    reason = "not_currently_adopted"
                else:
                    try:
                        if max(_date(row.get("material_available_at")), _date(row.get("knowledge_cutoff_at"))) > boundary:
                            reason = "future_material"
                        elif strict and max(_date(row.get("run_started_at")), _date(row.get("created_at"))) > boundary:
                            reason = "analysis_not_available_at_cutoff"
                    except ArchiveError:
                        reason = "unknown_availability"
                if reason:
                    exclusions.append({"snapshot_id": row["id"], "reason": reason})
                else:
                    eligible.append(row)
            eligible.sort(key=self._sort, reverse=True)
            policy = {'context_policy':'legacy_latest_adopted','policy_version':'legacy-v1.1'}
            loaded, history = eligible[:1], eligible[1:]
            if material is not None:
                from .annual_context import select_annual_context
                try:
                    if not material.get('form'):
                        raise ValueError('Current material form is required')
                    loaded, history, policy_exclusions, policy = select_annual_context(eligible,company,material,document_metadata or {})
                except (ValueError, KeyError, TypeError) as exc:
                    raise ArchiveError('Current material needs a valid form and period_end') from exc
                exclusions += policy_exclusions
            baseline = loaded[0] if loaded else None
            opinions, excluded_opinions = [], []
            if baseline:
                loaded_ids = {row['id'] for row in loaded}
                requested = {ref["comment_id"] for row in loaded for ref in row.get("inherited_comment_refs", []) if "comment_id" in ref}
                requested |= {key for key, versions in state["comments"].items() if versions[-1]["snapshot_id"] in loaded_ids}
                for key in sorted(requested):
                    versions = state["comments"].get(key)
                    if not versions:
                        excluded_opinions.append({"comment_id": key, "reason": "missing_opinion"})
                        continue
                    opinion = versions[-1]
                    source = state["snapshots"].get(opinion["snapshot_id"])
                    reason = None
                    if opinion.get("withdrawn") or not opinion.get("carry_forward"):
                        reason = "withdrawn_or_not_selected"
                    elif not source or source["status"] != "adopted":
                        reason = "origin_not_currently_adopted"
                    elif source["company_id"] != company or source["scope"] != scope or source.get('researcher_id') != researcher_id:
                        reason = "outside_research_scope"
                    elif strict and _date(opinion["available_at"]) > boundary:
                        reason = "opinion_not_available_at_cutoff"
                    elif _date(source["knowledge_cutoff_at"]) > boundary:
                        reason = "opinion_source_future_material"
                    if reason:
                        excluded_opinions.append({"comment_id": key, "reason": reason})
                    else:
                        selected = deepcopy(opinion)
                        selected.update(review_status="pending", review_required=True,
                                        epistemic_role="human_input_not_verified_fact")
                        opinions.append(selected)
            return {"company_id": company, "scope": scope, "researcher_id": researcher_id, "cutoff": cutoff, "strict": strict,
                    **policy,
                    "current_material": deepcopy(material),
                    "baseline_snapshot_id": baseline["id"] if baseline else None,
                    "baseline_snapshot_ids": [row['id'] for row in loaded],
                    "baseline_revision": baseline["revision"] if baseline else None,
                    "history_snapshot_ids": [row["id"] for row in history],
                    "opinions": opinions, "excluded_snapshots": exclusions, "excluded_opinions": excluded_opinions,
                    "inheritance_notices": [deepcopy(notice) for row in loaded for notice in row.get("inheritance_notices", [])],
                    "loaded_snapshot_ids": [row['id'] for row in loaded],
                    "history_loading": "on_demand", "opinion_review_status": "pending" if opinions else "not_applicable"}
