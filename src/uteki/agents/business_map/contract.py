from dataclasses import dataclass
from typing import Any

from uteki.domain.business_map import BusinessMap
from uteki.domain.documents import Document
from uteki.domain.runs import AgentRunRecord


@dataclass(frozen=True, slots=True)
class BusinessMapRequest:
    document: Document
    # Both None explicitly selects the complete document. The default remains
    # Item 1; a missing boundary must never silently expand a model's input.
    section_start: str | None = "ITEM 1. BUSINESS"
    section_end: str | None = "ITEM 1A. RISK FACTORS"


@dataclass(frozen=True, slots=True)
class AgentConfig:
    model: str
    prompt_version: str = "business-map-v0.1"
    temperature: float = 0.0


@dataclass(frozen=True, slots=True)
class BusinessMapAgentResult:
    candidate: BusinessMap
    run: AgentRunRecord
    # The adapter's exact response text when available, otherwise its payload.
    raw_output: Any


class BusinessMapRunError(ValueError):
    """A rejected run, including its audit record and any available model output.

    The caller owns persistence of both successful results and these failures.
    Keeping ValueError compatibility preserves existing validation callers.
    """

    def __init__(self, message: str, *, run: AgentRunRecord, raw_output: Any = None) -> None:
        super().__init__(message)
        self.run = run
        self.raw_output = raw_output
