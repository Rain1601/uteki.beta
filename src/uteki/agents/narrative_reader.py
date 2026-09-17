"""Compact transport only: never change immutable source blocks or evidence text."""
from copy import deepcopy
import json
from typing import Literal
from agents import function_tool
from pydantic import BaseModel
from uteki.agents.analysis_comparison import ToolSession
from uteki.agents.analysis_comparison import save
from uteki.agents.evidence_math import calculate


class CellReference(BaseModel):
    document_id: str
    index_id: str
    block_id: str
    row: int
    column: int
    row_label: str
    year: int


def compact_read(result):
    result = deepcopy(result)
    for block in result.get('blocks', []):
        # Locators stay in the frozen index. The agent needs identity, complete
        # text, page, semantic source metadata and table coordinates, not CSS.
        block.pop('style_signature', None)
        block.pop('dom_path', None)
        table = block.get('table')
        if table:
            cells = table.get('cells', [])
            table['original_cell_count'] = len(cells)
            table['rows'] = max((c['row'] + c.get('rowspan', 1) for c in cells), default=0)
            table['columns'] = max((c['column'] + c.get('colspan', 1) for c in cells), default=0)
            table['cells'] = [c for c in cells if c.get('text', '').strip() or c.get('xbrl')]
            table['transport_note'] = 'Empty cells omitted in this view only; coordinates/spans unchanged. Source index retains all cells.'
    result['transport_version'] = 'narrative-read-v1'
    return result


class CompactReader:
    def __init__(self, reader):
        self.reader = reader

    def __getattr__(self, name):
        return getattr(self.reader, name)

    def read(self, **args):
        return compact_read(self.reader.read(**args))


class NarrativeSession(ToolSession):
    def reader(self, doc_id):
        reader = super().reader(doc_id)
        return CompactReader(reader)

    def tools(self, stage):
        @function_tool
        def calculate_table(operation: Literal['growth_pct','ratio_pct'], first: CellReference,
                            second: CellReference, reason: str, decimals: int = 2) -> str:
            """Compute growth(current/prior) or ratio(numerator/denominator) from already-read cells.

            Use actual table row/column starts, exact row labels and year headers.
            Does not verify fiscal comparability, units or economic interpretation.
            """
            self.calls += 1
            self.stage_calls[stage] = self.stage_calls.get(stage,0)+1
            args = dict(operation=operation,first=first.model_dump(),second=second.model_dump(),decimals=decimals)
            try:
                if self.calls > self.max_calls:
                    raise ValueError('Tool call budget exhausted')
                if not reason.strip():
                    raise ValueError('Brief action reason required')
                result = calculate(self, **args)
                size = len(json.dumps(result,ensure_ascii=False))
                if self.chars+size > self.max_chars:
                    raise ValueError('Tool payload budget exhausted')
                self.chars += size
            except (ValueError, KeyError, StopIteration) as exc:
                result = {'error':type(exc).__name__, 'message':str(exc) if isinstance(exc,ValueError) else 'Invalid cell reference'}
            save(self.folder/f'tool-{self.calls:03}.json',dict(stage=stage,tool='calculate_table',reason=reason,arguments=args,result=result))
            return json.dumps(result,ensure_ascii=False)
        return super().tools(stage) + [calculate_table]
