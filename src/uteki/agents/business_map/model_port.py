from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ModelResponse:
    payload: dict[str, Any]
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class StructuredModel(Protocol):
    def generate_json(self, *, system: str, user: str, model: str, temperature: float) -> ModelResponse: ...

