from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AgentRunRecord:
    run_id: str
    agent_id: str
    agent_version: str
    document_id: str
    model: str
    prompt_version: str
    prompt_hash: str
    configuration: dict[str, Any]
    status: RunStatus
    started_at: str
    finished_at: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

