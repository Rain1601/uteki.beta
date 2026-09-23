"""Bounded, pinned-source reading and citation provenance session."""
import json
from pathlib import Path
from agents import function_tool
from .document_reader import DocumentReader


def save(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, default=lambda obj: obj.model_dump(mode='json'))


class ToolSession:
    def __init__(self, root, manifest, folder, max_calls=30, max_chars=150000):
        self.root, self.manifest, self.folder = Path(root), manifest, Path(folder)
        self.readers = {}
        self.evidence = {}
        self.stage_evidence = {}
        self.stage_calls = {}
        self.calls, self.chars = 0, 0
        self.max_calls, self.max_chars = max_calls, max_chars

    def reader(self, doc_id):
        if doc_id not in self.readers:
            doc = next(d for d in self.manifest['documents'] if d['id'] == doc_id)
            self._check_date(doc)
            reader = DocumentReader(self.root / doc['index_folder'])
            if reader.manifest != self.manifest['indexes'][doc_id]:
                raise ValueError('Pinned index changed')
            self.readers[doc_id] = reader
        return self.readers[doc_id]

    def _check_date(self, doc):
        cutoff = self.manifest.get('material_cutoff')
        if cutoff:
            from datetime import date
            published = doc.get('published_at') or doc.get('filed_at')
            if not published or date.fromisoformat(published) > date.fromisoformat(cutoff):
                raise ValueError('Material after cutoff or publication date unknown')

    def call(self, stage, tool, reason, **args):
        self.calls += 1
        self.stage_calls[stage] = self.stage_calls.get(stage,0)+1
        if self.calls > self.max_calls:
            save(self.folder/f'tool-{self.calls:03}.json', {'stage':stage,'tool':tool,'reason':reason,'arguments':args,'result':{'error':'budget_exhausted'}})
            raise RuntimeError('Tool call budget exhausted')
        try:
            if not reason.strip(): raise ValueError('Brief action reason required')
            if tool == 'documents':
                for doc in self.manifest['documents']:
                    self._check_date(doc)
                result = [{k:d.get(k) for k in ('id','form','period_end','filed_at','published_at','title','status')}
                          for d in self.manifest['documents'] if not args['form'] or d['form'] == args['form']]
            else:
                params = dict(args)
                doc_id = params.pop('document_id')
                result = getattr(self.reader(doc_id), tool)(**params)
                result['document_id'] = doc_id
            size = len(json.dumps(result, ensure_ascii=False))
            if size > 60000 or self.chars + size > self.max_chars:
                raise ValueError('Tool payload budget exceeded; narrow scope or reduce count')
            self.chars += size
            if tool == 'read':
                for b in result['blocks']:
                    self.evidence[(doc_id,result['index_id'],b['block_id'])] = b['text']
                    self.stage_evidence.setdefault(stage,{})[(doc_id,result['index_id'],b['block_id'])] = b['text']
        except Exception as exc:
            result = {'error': type(exc).__name__, 'message': str(exc) if isinstance(exc,ValueError) else 'Unknown document/node/block'}
        save(self.folder/f'tool-{self.calls:03}.json', {'stage':stage,'tool':tool,'reason':reason,'arguments':args,'result':result})
        return result

    def tools(self, stage):
        @function_tool
        def documents(reason: str, form: str = '') -> str:
            """List pinned materials: filings, EARNINGS_CALL, EARNINGS_RELEASE. Empty form lists all."""
            return json.dumps(self.call(stage,'documents',reason,form=form),ensure_ascii=False)

        @function_tool
        def outline(document_id: str, reason: str) -> str:
            """Get the source directory: Part/Item for filings; speaker/Q&A for calls. No full text."""
            return json.dumps(self.call(stage,'outline',reason,document_id=document_id),ensure_ascii=False)

        @function_tool
        def search(document_id: str, node_id: str, query: str, reason: str, offset: int = 0, limit: int = 8) -> str:
            """Literal phrase search inside a chosen node, paginated in source order. Read hits to cite."""
            return json.dumps(self.call(stage,'search',reason,document_id=document_id,node_id=node_id,query=query,offset=offset,limit=limit),ensure_ascii=False)

        @function_tool
        def read(document_id: str, node_id: str, start_block_id: str, reason: str, count: int = 1) -> str:
            """Read complete blocks plus list/table/speaker or full Q&A context; count 1..12. May expand."""
            return json.dumps(self.call(stage,'read',reason,document_id=document_id,node_id=node_id,start_block_id=start_block_id,count=count),ensure_ascii=False)
        return [documents, outline, search, read]

    def resolve_citations(self, answer, stage=None):
        """Source excerpts are compiled from read blocks, never model-reconstructed text.

        Whole blocks intentionally preserve table headers/columns. This establishes
        provenance only; it does not establish that a block supports a claim.
        """
        answer = answer.model_copy(deep=True)
        ledger = self.stage_evidence.get(stage, {}) if stage else self.evidence
        for claim in answer.claims:
            for citation in claim.citations:
                key = (citation.document_id, citation.index_id, citation.block_id)
                if key in ledger:
                    citation.quote = ledger[key]
        return answer

    def validate(self, answer, stage=None):
        errors=[]
        ledger=self.stage_evidence.get(stage,{}) if stage else self.evidence
        if answer.status == 'answered' and not answer.claims: errors.append('No claims')
        for claim in answer.claims:
            if not claim.citations: errors.append('Uncited claim: '+claim.text)
            for c in claim.citations:
                text=ledger.get((c.document_id,c.index_id,c.block_id))
                if not c.quote.strip() or text is None or c.quote not in text:
                    errors.append('Unread/invalid exact quote: '+c.block_id)
        if not (self.stage_calls.get(stage,0) if stage else self.calls): errors.append('No material inspection')
        return errors
