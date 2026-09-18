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
    raw_output: Any = None


class ModelGenerationError(RuntimeError):
    """Adapter failure with optional provider output and known usage.

    Adapters should retain malformed JSON here instead of discarding it. Unknown
    usage remains None, including when a provider may have billed a failed call.
    """

    def __init__(
        self,
        message: str,
        *,
        raw_output: Any = None,
        model: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cost_usd: float | None = None,
    ) -> None:
        super().__init__(message)
        self.raw_output = raw_output
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cost_usd = cost_usd


class StructuredModel(Protocol):
    def generate_json(self, *, system: str, user: str, model: str, temperature: float) -> ModelResponse: ...
