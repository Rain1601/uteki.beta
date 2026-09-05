from dataclasses import dataclass

from uteki.domain.business_map import BusinessMap
from uteki.domain.documents import Document
from uteki.domain.runs import AgentRunRecord


@dataclass(frozen=True, slots=True)
class BusinessMapRequest:
    document: Document
    section_start: str = "ITEM 1. BUSINESS"
    section_end: str = "ITEM 1A. RISK FACTORS"


@dataclass(frozen=True, slots=True)
class AgentConfig:
    model: str
    prompt_version: str = "business-map-v0.1"
    temperature: float = 0.0


@dataclass(frozen=True, slots=True)
class BusinessMapAgentResult:
    candidate: BusinessMap
    run: AgentRunRecord
    raw_output: dict

