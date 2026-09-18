from __future__ import annotations

import hashlib
import json
import math
import re
import time
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from uteki.domain.business_map import BusinessMap, business_map_from_dict
from uteki.domain.documents import Document, Paragraph
from uteki.domain.runs import AgentRunRecord, RunStatus

from .contract import AgentConfig, BusinessMapAgentResult, BusinessMapRequest, BusinessMapRunError
from .model_port import ModelGenerationError, ModelResponse, StructuredModel
from .prompts import (SYSTEM_PROMPT_V0_1, SYSTEM_PROMPT_V0_2,
                      render_user_prompt, render_user_prompt_v0_2)


def _now() -> str:
    return datetime.now(UTC).isoformat()


_PROMPTS = {
    "business-map-v0.1": (SYSTEM_PROMPT_V0_1, render_user_prompt),
    "business-map-v0.2": (SYSTEM_PROMPT_V0_2, render_user_prompt_v0_2),
}


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _json_safe(value: Any, ancestors: frozenset[int] = frozenset()) -> Any:
    """Copy audit values without losing a failure to invalid JSON metadata.

    Invalid values are descriptions, never invented valid usage or config.
    The original response remains separately available as raw_output.
    """
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    if id(value) in ancestors:
        return {"invalid_type": "circular_reference"}
    nested = ancestors | {id(value)}
    if isinstance(value, dict):
        if all(isinstance(key, str) for key in value):
            return {key: _json_safe(item, nested) for key, item in value.items()}
        return {"invalid_type": "dict_with_nonstring_keys",
                "entries": [[_json_safe(key, nested), _json_safe(item, nested)]
                            for key, item in value.items()]}
    if isinstance(value, list):
        return [_json_safe(item, nested) for item in value]
    try:
        representation = repr(value)
    except Exception:
        representation = "<unrepresentable>"
    return {"invalid_type": type(value).__name__, "representation": representation}


def _validate_json(value: Any, path: str, ancestors: frozenset[int] = frozenset()) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    if id(value) in ancestors:
        raise ValueError(f"{path} contains a circular reference")
    nested = ancestors | {id(value)}
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError(f"{path} keys must be strings")
        for key, item in value.items():
            _validate_json(item, f"{path}.{key}", nested)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json(item, f"{path}[{index}]", nested)
        return
    raise ValueError(f"{path} must contain only finite JSON values")


def _finite_number(value: Any) -> bool:
    return (isinstance(value, int) and not isinstance(value, bool)
            or isinstance(value, float) and math.isfinite(value))


def _usage_issues(usage: ModelResponse | ModelGenerationError | None) -> dict[str, str]:
    issues = {}
    for name in ("input_tokens", "output_tokens"):
        value = getattr(usage, name, None)
        if value is not None and (type(value) is not int or value < 0):
            issues[name] = "must be a nonnegative integer or null"
    value = getattr(usage, "cost_usd", None)
    if value is not None and (not _finite_number(value) or value < 0):
        issues["cost_usd"] = "must be a finite nonnegative number or null"
    return issues


def _validate_document(document: Document) -> None:
    for name in ("id", "source_url", "content_hash"):
        value = getattr(document, name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"document.{name} must be a nonempty string")
    seen = set()
    for paragraph in document.paragraphs:
        if type(paragraph.ordinal) is not int or paragraph.ordinal < 1:
            raise ValueError("paragraph ordinal must be a positive integer")
        if paragraph.ordinal in seen:
            raise ValueError(f"duplicate paragraph ordinal: {paragraph.ordinal}")
        seen.add(paragraph.ordinal)
        if not isinstance(paragraph.text, str):
            raise ValueError(f"paragraph {paragraph.ordinal} text must be a string")
        normalized = re.sub(r"\s+", " ", paragraph.text).strip()
        actual_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        if paragraph.text_hash != actual_hash:
            raise ValueError(f"paragraph {paragraph.ordinal} text hash does not match source text")


def _section_indices(document: Document, start: str | None, end: str | None) -> tuple[int, int]:
    if start is None and end is None:
        if not document.paragraphs:
            raise ValueError("full-document input must contain paragraphs")
        return 0, len(document.paragraphs)
    if start is None or end is None:
        raise ValueError("section_start and section_end must both be None for full-document input")
    if not isinstance(start, str) or not start.strip() or not isinstance(end, str) or not end.strip():
        raise ValueError("section boundaries must be nonempty strings or both None")
    start_indices = [i for i, paragraph in enumerate(document.paragraphs) if paragraph.text == start]
    if not start_indices:
        raise ValueError(f"section start not found: {start}")
    start_index = start_indices[0]
    end_indices = [
        i for i, paragraph in enumerate(document.paragraphs)
        if i > start_index and paragraph.text == end
    ]
    if not end_indices:
        raise ValueError(f"section end not found after start: {end}")
    return start_index, end_indices[0]


def select_section(document: Document, start: str | None, end: str | None) -> tuple[Paragraph, ...]:
    start_index, end_index = _section_indices(document, start, end)
    return document.paragraphs[start_index:end_index]


def validate_evidence(
    candidate: BusinessMap, document: Document, paragraphs: tuple[Paragraph, ...] | None = None
) -> None:
    supplied = document.paragraphs if paragraphs is None else paragraphs
    by_ordinal = {paragraph.ordinal: paragraph for paragraph in supplied}
    for evidence in candidate.evidence:
        paragraph = by_ordinal.get(evidence.paragraph_ordinal)
        if paragraph is None:
            raise ValueError(f"evidence {evidence.id} references a paragraph not supplied to the model")
        if paragraph.text_hash != evidence.text_hash:
            raise ValueError(f"evidence {evidence.id} text hash does not match source")
        if evidence.document_id != document.id:
            raise ValueError(f"evidence {evidence.id} references a different document")
        if evidence.source_url != document.source_url:
            raise ValueError(f"evidence {evidence.id} source_url does not match source")


def _object(value: Any, path: str, required: set[str], optional: set[str] | None = None) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    missing = required - value.keys()
    extra = value.keys() - required - (optional or set())
    if missing or extra:
        raise ValueError(f"{path} invalid fields: missing={sorted(missing)}, unsupported={sorted(extra)}")
    return value


def _strings(value: dict, path: str, fields: tuple[str, ...]) -> None:
    for field in fields:
        if not isinstance(value[field], str):
            raise ValueError(f"{path}.{field} must be a string")


def _array(value: Any, path: str, *, strings: bool = False) -> list:
    if not isinstance(value, list) or (strings and any(not isinstance(item, str) for item in value)):
        raise ValueError(f"{path} must be an array{' of strings' if strings else ''}")
    return value


def _validate_payload(payload: Any, *, allow_derived: bool = True) -> None:
    """Validate the model boundary without changing the stored/reviewed map parser."""
    required = {"schema_version", "company_id", "document_id", "summary", "businesses", "relationships", "unknowns", "evidence"}
    root = _object(payload, "candidate", required, {"metadata"})
    _strings(root, "candidate", ("schema_version", "company_id", "document_id", "summary"))
    if root["schema_version"] != "0.1":
        raise ValueError("candidate.schema_version must be 0.1")
    if not root["company_id"].strip():
        raise ValueError("candidate.company_id must not be empty")
    # Provenance, evaluation, and adoption metadata belong to the host/reviewer.
    if "metadata" in root and (not isinstance(root["metadata"], dict) or root["metadata"]):
        raise ValueError("model candidate metadata must be empty; review and adoption are external")
    specifications = {
        "businesses": (
            {"id", "name", "kind", "description", "evidence_ids"},
            {"products_services", "customers", "monetization", "importance_signals", "review_status"},
            ("id", "name", "kind", "description"),
            ("products_services", "customers", "importance_signals", "evidence_ids"),
        ),
        "relationships": (
            {"source_id", "target_id", "kind", "description", "evidence_ids"}, {"review_status"},
            ("source_id", "target_id", "kind", "description"), ("evidence_ids",),
        ),
        "unknowns": (
            {"id", "question", "materiality", "related_business_ids", "reason_unanswered"}, {"evidence_ids"},
            ("id", "question", "materiality", "reason_unanswered"), ("related_business_ids", "evidence_ids"),
        ),
        "evidence": (
            {"id", "document_id", "section_path", "paragraph_ordinal", "text_hash", "source_url", "support"}, set(),
            ("id", "document_id", "text_hash", "source_url", "support"), ("section_path",),
        ),
    }
    for collection, (required_fields, optional_fields, strings, arrays) in specifications.items():
        for index, item in enumerate(_array(root[collection], collection)):
            path = f"{collection}[{index}]"
            _object(item, path, required_fields, optional_fields)
            _strings(item, path, strings)
            for field in arrays:
                if field in item:
                    _array(item[field], f"{path}.{field}", strings=True)
            if item.get("review_status", "candidate") != "candidate":
                raise ValueError(f"{path}.review_status must remain candidate")
            if collection == "evidence" and type(item["paragraph_ordinal"]) is not int:
                raise ValueError(f"{path}.paragraph_ordinal must be an integer")
            if collection == "businesses":
                for number, statement in enumerate(_array(item.get("monetization", []), f"{path}.monetization")):
                    statement_path = f"{path}.monetization[{number}]"
                    _object(statement, statement_path, {"description", "basis", "evidence_ids"})
                    _strings(statement, statement_path, ("description", "basis"))
                    if not allow_derived and statement["basis"] == "derived":
                        raise ValueError(f"{statement_path}.basis cannot be derived: "
                                         "the request supplies no approved deterministic derivation rules")
                    _array(statement["evidence_ids"], f"{statement_path}.evidence_ids", strings=True)


class BusinessMapAgent:
    agent_id = "business-map-agent"
    agent_version = "0.2.0"

    def __init__(self, model: StructuredModel) -> None:
        self.model = model

    def run(self, request: BusinessMapRequest, config: AgentConfig) -> BusinessMapAgentResult:
        started_at = _now()
        started = time.perf_counter()
        run_id = str(uuid.uuid4())
        prompt_version = ""
        prompt_hash = ""
        input_hash = None
        input_manifest: dict[str, Any] = {}
        response = None
        raw_output = None
        stage = "configuration"
        configuration = {
            "requested_model": config.model,
            "requested_prompt_version": config.prompt_version,
            "temperature": config.temperature,
            "section_start": request.section_start,
            "section_end": request.section_end,
        }

        def record(status: RunStatus, error: Exception | None = None) -> AgentRunRecord:
            usage = response if isinstance(response, ModelResponse) else error if isinstance(error, ModelGenerationError) else None
            issues = _usage_issues(usage)
            saved_configuration = _json_safe(configuration)
            if issues:
                saved_configuration["invalid_usage"] = {
                    name: {"value": _json_safe(getattr(usage, name)), "reason": reason}
                    for name, reason in issues.items()
                }
            reported_model = getattr(usage, "model", None)
            actual_model = reported_model if isinstance(reported_model, str) and reported_model.strip() else None
            return AgentRunRecord(
                run_id=run_id,
                agent_id=self.agent_id,
                agent_version=self.agent_version,
                document_id=request.document.id if isinstance(request.document.id, str) else "",
                model=actual_model or (config.model if isinstance(config.model, str) else ""),
                prompt_version=prompt_version,
                prompt_hash=prompt_hash,
                configuration=saved_configuration,
                status=status,
                started_at=started_at,
                finished_at=_now(),
                latency_ms=round((time.perf_counter() - started) * 1000),
                input_tokens=None if "input_tokens" in issues else getattr(usage, "input_tokens", None),
                output_tokens=None if "output_tokens" in issues else getattr(usage, "output_tokens", None),
                cost_usd=None if "cost_usd" in issues else getattr(usage, "cost_usd", None),
                input_hash=input_hash,
                input_manifest=deepcopy(input_manifest),
                error_stage=stage if error is not None else None,
                error_type=type(error).__name__ if error is not None else None,
                error_message=str(error) if error is not None else None,
            )

        try:
            if config.prompt_version not in _PROMPTS:
                raise ValueError(f"unsupported prompt_version: {config.prompt_version}")
            prompt_version = config.prompt_version
            system_prompt, renderer = _PROMPTS[prompt_version]
            if not isinstance(config.model, str) or not config.model.strip():
                raise ValueError("model must be a nonempty string")
            if not _finite_number(config.temperature):
                raise ValueError("temperature must be a finite number")
            stage = "input"
            _validate_document(request.document)
            start_index, end_index = _section_indices(request.document, request.section_start, request.section_end)
            paragraphs = request.document.paragraphs[start_index:end_index]
            input_manifest = {
                "schema_version": "business-map-input-v1",
                "document_id": request.document.id,
                "source_url": request.document.source_url,
                "source_content_hash": request.document.content_hash,
                "selection_mode": "full_document" if request.section_start is None else "section",
                "section_start": request.section_start,
                "section_end": request.section_end,
                "start_ordinal": paragraphs[0].ordinal,
                "end_ordinal_exclusive": (request.document.paragraphs[end_index].ordinal
                                          if end_index < len(request.document.paragraphs)
                                          else paragraphs[-1].ordinal + 1),
                "paragraph_count": len(paragraphs),
                "paragraphs": [
                    {"ordinal": paragraph.ordinal, "text": paragraph.text, "text_hash": paragraph.text_hash}
                    for paragraph in paragraphs
                ],
            }
            input_hash = _fingerprint(input_manifest)
            user_prompt = renderer(request.document.id, request.document.source_url, paragraphs)
            prompt_hash = _fingerprint({"system": system_prompt, "user": user_prompt})
            stage = "model"
            response = self.model.generate_json(
                system=system_prompt, user=user_prompt, model=config.model, temperature=config.temperature,
            )
            if not isinstance(response, ModelResponse):
                raw_output = deepcopy(response)
                raise ValueError("model must return ModelResponse")
            raw_output = deepcopy(response.raw_output if response.raw_output is not None else response.payload)
            configuration["reported_model"] = response.model
            configuration["model_metadata"] = response.metadata
            if not isinstance(response.model, str) or not response.model.strip():
                raise ValueError("ModelResponse.model must identify the actual model")
            if not isinstance(response.metadata, dict):
                raise ValueError("ModelResponse.metadata must be an object")
            _validate_json(response.metadata, "ModelResponse.metadata")
            usage_issues = _usage_issues(response)
            if usage_issues:
                raise ValueError("invalid ModelResponse usage: " + "; ".join(
                    f"{name} {reason}" for name, reason in usage_issues.items()))
            stage = "schema"
            _validate_payload(response.payload, allow_derived=prompt_version == "business-map-v0.1")
            candidate = business_map_from_dict(deepcopy(response.payload))
            stage = "evidence"
            if candidate.document_id != request.document.id:
                raise ValueError("candidate document_id does not match request")
            validate_evidence(candidate, request.document, paragraphs)
            run = record(RunStatus.SUCCEEDED)
            return BusinessMapAgentResult(candidate=candidate, run=run, raw_output=raw_output)
        except Exception as error:
            if raw_output is None:
                raw_output = deepcopy(getattr(error, "raw_output", None))
                if isinstance(error, json.JSONDecodeError):
                    raw_output = error.doc
            raise BusinessMapRunError(str(error), run=record(RunStatus.FAILED, error), raw_output=raw_output) from error
