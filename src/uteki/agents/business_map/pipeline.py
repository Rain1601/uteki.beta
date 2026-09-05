from __future__ import annotations

import hashlib
import time
import uuid
from datetime import UTC, datetime

from uteki.domain.business_map import BusinessMap, business_map_from_dict
from uteki.domain.documents import Document, Paragraph
from uteki.domain.runs import AgentRunRecord, RunStatus

from .contract import AgentConfig, BusinessMapAgentResult, BusinessMapRequest
from .model_port import StructuredModel
from .prompts import SYSTEM_PROMPT_V0_1, render_user_prompt


def _now() -> str:
    return datetime.now(UTC).isoformat()


def select_section(document: Document, start: str, end: str) -> tuple[Paragraph, ...]:
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
    return document.paragraphs[start_index:end_indices[0]]


def validate_evidence(candidate: BusinessMap, document: Document) -> None:
    by_ordinal = {paragraph.ordinal: paragraph for paragraph in document.paragraphs}
    for evidence in candidate.evidence:
        paragraph = by_ordinal.get(evidence.paragraph_ordinal)
        if paragraph is None:
            raise ValueError(f"evidence {evidence.id} has unknown paragraph ordinal")
        if paragraph.text_hash != evidence.text_hash:
            raise ValueError(f"evidence {evidence.id} text hash does not match source")
        if evidence.document_id != document.id:
            raise ValueError(f"evidence {evidence.id} references a different document")


class BusinessMapAgent:
    agent_id = "business-map-agent"
    agent_version = "0.1.0"

    def __init__(self, model: StructuredModel) -> None:
        self.model = model

    def run(self, request: BusinessMapRequest, config: AgentConfig) -> BusinessMapAgentResult:
        paragraphs = select_section(request.document, request.section_start, request.section_end)
        user_prompt = render_user_prompt(request.document.id, request.document.source_url, paragraphs)
        prompt_hash = hashlib.sha256((SYSTEM_PROMPT_V0_1 + user_prompt).encode()).hexdigest()
        started_at = _now()
        started = time.perf_counter()
        response = self.model.generate_json(
            system=SYSTEM_PROMPT_V0_1,
            user=user_prompt,
            model=config.model,
            temperature=config.temperature,
        )
        candidate = business_map_from_dict(response.payload)
        if candidate.document_id != request.document.id:
            raise ValueError("candidate document_id does not match request")
        validate_evidence(candidate, request.document)
        finished_at = _now()
        run = AgentRunRecord(
            run_id=str(uuid.uuid4()),
            agent_id=self.agent_id,
            agent_version=self.agent_version,
            document_id=request.document.id,
            model=response.model,
            prompt_version=config.prompt_version,
            prompt_hash=prompt_hash,
            configuration={"temperature": config.temperature},
            status=RunStatus.SUCCEEDED,
            started_at=started_at,
            finished_at=finished_at,
            latency_ms=round((time.perf_counter() - started) * 1000),
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=response.cost_usd,
        )
        return BusinessMapAgentResult(candidate=candidate, run=run, raw_output=response.payload)

