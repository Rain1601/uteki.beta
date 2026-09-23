"""Named sections prevent duplicate/missing categories without prescribing reasoning."""
from pydantic import BaseModel, Field
from typing import Literal
from uteki.agents.reading.citations import Citation

SECTIONS = ('business', 'industry', 'earnings', 'valuation', 'watch')


class NarrativeParagraph(BaseModel):
    text: str
    kind: Literal['fact', 'inference', 'unknown']
    citations: list[Citation]


class NarrativeSection(BaseModel):
    title: str = Field(description='简短阅读标题，不要把整段核心判断写进标题')
    paragraphs: list[NarrativeParagraph] = Field(min_length=1)


class AnnualNarrative(BaseModel):
    title: str
    thesis: NarrativeParagraph
    business: NarrativeSection
    industry: NarrativeSection
    earnings: NarrativeSection
    valuation: NarrativeSection
    watch: NarrativeSection
    limitations: list[str]
    stop_reason: str

    def reading_payload(self):
        payload = self.model_dump()
        payload['sections'] = [{'key':key, **payload.pop(key)} for key in SECTIONS]
        return payload
