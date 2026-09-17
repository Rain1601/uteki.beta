"""Explicit archive rerun entry point. Never runs on note save or adoption."""
import json
import hashlib
from pathlib import Path
from .material_library import load_catalog, pin_materials
from .research_archive import ArchiveError
from .research_archive_context import build_context


async def run_archive_revision(root, store, output, *, source_id, document_ids,
                               question, model, provider, strict=False):
    """Prepare and execute one isolated revision; no automatic adoption.

    Caller chooses materials/model/provider and authorizes the paid run.
    Present-day revisions of historical work are retrospective, not blind tests.
    """
    from .analysis_comparison import run_mode
    from .call_costs import pricing_snapshot
    rows=store.list()
    source=next((r for r in rows if r['id']==source_id),None)
    if not source or source['status']=='deleted' or source.get('researcher_id','unassigned')=='unassigned':
        raise ArchiveError('Choose an available report with a verified researcher')
    if source.get('mode') not in {'single','team'}:
        raise ArchiveError('Unknown researcher execution mode')
    if not isinstance(question,str) or not question.strip():
        raise ArchiveError('Explicit research question required')
    docs={d['id']:d for d in load_catalog(root)['documents']}
    material=docs.get(source['primary_document_id'])
    if not material or material['id'] not in document_ids:
        raise ArchiveError('Include the original primary material in the rerun')
    cutoff=source['knowledge_cutoff_at'][:10]
    context=build_context(store,source['company_id'],source['scope'],cutoff,strict=strict,
                          researcher_id=source['researcher_id'],material=material,
                          document_metadata=docs,rerun_from=source_id)
    manifest=pin_materials(root,cutoff,document_ids)
    manifest.update(provider=provider,model=model,citation_mode='source_block',
                    pricing_snapshot=pricing_snapshot(provider,model),
                    researcher_id=source['researcher_id'],scope=source['scope'],
                    rerun_from=source_id,question=question,mode=source['mode'])
    await run_mode(root,manifest,output,question,model,source['mode'],research_context=context)
    status='failed' if (Path(output)/'failure.json').exists() else json.loads((Path(output)/'result.json').read_text())['status']
    archived = None
    result_path = Path(output)/'result.json'
    if result_path.exists() and not (Path(output)/'failure.json').exists():
        result = json.loads(result_path.read_text())
        if isinstance(result.get('answer'), dict) and result['answer']:
            archived = store.record_agent_revision(source_id, source['revision'],
                answer=result['answer'], reason=question, agent_id=source['researcher_id'],
                model=model, run_id=str(Path(output).resolve()),
                artifact_path=result_path.resolve(),
                artifact_sha256=hashlib.sha256(result_path.read_bytes()).hexdigest(),
                citation_errors=result.get('citation_errors', []))['snapshot']['id']
    return {'run_folder':str(Path(output)), 'context_id':context['context_id'],
            'snapshot_id': archived,
            'status':status,
            'automatic_adoption':False}
