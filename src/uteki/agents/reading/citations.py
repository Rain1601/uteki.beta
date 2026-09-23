"""Citation and claim contracts shared by historical analysis consumers."""
from typing import Literal
from pydantic import BaseModel


class Citation(BaseModel):
    document_id: str
    index_id: str
    block_id: str
    quote: str


class Claim(BaseModel):
    text: str
    citations: list[Citation]


class Answer(BaseModel):
    status: Literal['answered', 'insufficient_material']
    claims: list[Claim]
    limitations: list[str]
    findings: list[str]
    stop_reason: str
