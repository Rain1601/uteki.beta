"""Freeze and run source-only prompt A/B. Evaluation targets never enter requests."""
import argparse
import asyncio
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import shutil

from agents import Agent, AgentOutputSchema, ModelSettings, Runner, RunConfig
from uteki.agents.runtime.model_factory import model_adapter
from uteki.agents.runtime.call_costs import MeteredModel, pricing_snapshot, summarize
from uteki.agents.runtime.deepseek_model import json_instructions
from uteki.agents.reading.document_reader import DocumentReader
from uteki.agents.runtime.local_credentials import load_provider_key
from uteki.agents.runtime.run_budget import RunBudget, BudgetExceeded
from uteki.infrastructure.research_data.extraction_prompts import Extraction, PROMPTS, validate_extraction
from uteki.infrastructure.research_data.financial_records import digest
from run_research_data_consumer_comparison import verify_prepared, save
from run_research_data_steps import verify_sources, SPECS

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '574ed3624aebd0418c7e96cd101262f30210ab26'
UPSTREAM_PATHS = {
    'earnings-preview.md': 'plugins/partner-built/spglobal/skills/earnings-preview-beta/SKILL.md',
    'tear-sheet.md': 'plugins/partner-built/spglobal/skills/tear-sheet/SKILL.md',
    'transcript-reader.yaml': 'managed-agent-cookbooks/earnings-reviewer/subagents/transcript-reader.yaml',
    'LICENSE': 'LICENSE',
}
TASKS = {
    'F1': 'Extract Google Cloud revenue and operating_income for all presented quarterly and six-month periods. '
          'Use metric names revenue and operating_income. No other metrics or calculated values.',
    'T1': 'Extract consolidated CapEx guidance and investment rationale, Google Cloud growth outlook, '
          'and infrastructure/depreciation outlook from the provided prepared remarks. '
          'Use metric names capex_guidance, investment_rationale, cloud_growth_outlook, '
          'infrastructure_expense_pressure and depreciation_outlook. No unrelated metrics.',
    'T2': 'Extract the CapEx composition, asset useful life and Cloud allocation statements from this Q&A. '
          'Use metric names capex_machine_share, capex_long_duration_share, building_useful_life '
          'and cloud_ml_compute_share. Preserve the relevant analyst question references. '
          'Do not extract the unrelated commerce discussion.',
}


def prepare(output, candidate, upstream):
    verify_sources()
    verify_prepared(candidate)
    output.mkdir(parents=True, exist_ok=False)
    upstream_manifest = []
    for name, path in UPSTREAM_PATHS.items():
        target = output/'upstream'/name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(upstream/name, target)
        upstream_manifest.append({'file': 'upstream/'+name, 'sha256': digest(target.read_bytes()),
                                  'url': f'https://github.com/anthropics/financial-services/blob/{COMMIT}/{path}'})
    save(output/'upstream.json', {'commit': COMMIT, 'files': upstream_manifest,
         'adaptations': ['S&P tool inputs replaced by immutable local source blocks',
                        'Four curated quotes replaced by all relevant records in the bounded case',
                        'Quantitative-only guidance extended to qualitative outlook and linked qualifications',
                        'No reports, trading views, commercial queries or model file access',
                        'Persistence enforced by host in BOTH arms; not a prompt treatment effect']})
    call_dir, index = SPECS['call']
    reader = DocumentReader(ROOT/call_dir/index)
    call_manifest = json.loads((ROOT/call_dir/'manifest.json').read_text())
    a1 = json.loads((candidate/'step-05/A1/before-input.json').read_text())
    cases = {'F1': a1}
    for case in ('T1', 'T2'):
        selected = [b for b in reader.blocks if
                    (case == 'T2' and b.get('exchange_id') == 'qa-06') or
                    (case == 'T1' and (b['block_id'].startswith(('block-000019-', 'block-000020-'))
                     or 145 <= int(b['block_id'].split('-')[1]) <= 155))]
        cases[case] = {
            'document_id': call_manifest['document_id'], 'index_id': reader.index['index_id'],
            'document_period': 'FY2025Q4', 'published_at': call_manifest['published_at'],
            'blocks': [{k: b.get(k) for k in ('block_id', 'text', 'speaker', 'speaker_role', 'exchange_id')}
                       for b in selected]}
    for case, packet in cases.items():
        packet['entity_catalog'] = [
            {'entity_id': 'alphabet', 'label': 'Alphabet Inc.', 'scope': 'consolidated'},
            {'entity_id': 'google-cloud', 'label': 'Google Cloud', 'scope': 'reported_segment'}]
        save(output/'cases'/f'{case}.json', {'task': TASKS[case], 'packet': packet})
    for arm, prompt in PROMPTS.items():
        target = output/'prompts'/f'{arm}.txt'
        target.parent.mkdir(exist_ok=True)
        target.write_text(prompt)
    save(output/'schema.json', AgentOutputSchema(Extraction).json_schema())
    save(output/'protocol.json', {
        'created_at': datetime.now(timezone.utc).isoformat(), 'version': 'extraction-prompt-ab-v0.2',
        'model': 'deepseek-flash', 'provider': 'deepseek', 'thinking': 'disabled', 'temperature': 0,
        'max_tokens': 6000, 'max_requests': 12, 'repeats': 2, 'budget_usd': '0.5',
        'arms': list(PROMPTS), 'cases': list(TASKS), 'same_source_schema_model': True,
        'treatment': 'Additional extraction workflow instructions only',
        'control': 'New task/schema-compatible control, NOT a historical Uteki prompt replay',
        'scope': 'One table, selected prepared remarks, one complete Q&A; not full-document recall',
        'review': 'Pre-call source-reviewed checklist; agent review, not independent human Gold',
        'consumer_budget_usd': '0.5',
        'candidate_manifest_sha256': digest((candidate/'manifest.json').read_bytes()),
        'criteria': ['numeric entity/metric/period/unit/value agreement', 'exact quotes and speakers',
                     'guidance versus actual', 'qualifications linked to the relevant record',
                     'coverage of requested statements', 'no analyst claims or denominator substitution',
                     'input/output tokens, latency, estimated cost', 'both repetitions, no best-run selection']})
    files = {str(p.relative_to(output)): digest(p.read_bytes()) for p in output.rglob('*') if p.is_file()}
    save(output/'manifest.json', {'files': files})


async def run(prepared, output):
    verify_prepared(prepared)
    protocol = json.loads((prepared/'protocol.json').read_text())
    if protocol['version'] != 'extraction-prompt-ab-v0.2':
        raise ValueError('Prepare a new protocol with explicit entity catalogs; preserve the historical run')
    if json.loads((prepared/'schema.json').read_text()) != AgentOutputSchema(Extraction).json_schema():
        raise ValueError('Frozen schema differs from runtime schema')
    output.mkdir(parents=True, exist_ok=False)
    model, provider = protocol['model'], protocol['provider']
    pricing = pricing_snapshot(provider, model)
    if not pricing:
        raise ValueError('Checked price required')
    budget = RunBudget(output/'budget.sqlite', protocol['budget_usd'])
    save(output/'manifest.json', {'protocol': protocol, 'pricing': pricing,
         'prepared_path': str(prepared.resolve()),
         'prepared_manifest_sha256': digest((prepared/'manifest.json').read_bytes()),
         'started_at': datetime.now(timezone.utc).isoformat(),
         'sdk': importlib.metadata.version('openai-agents'), 'client': importlib.metadata.version('openai'),
         'code_sha256': {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in (
             Path(__file__).resolve(), ROOT/'src/uteki/infrastructure/research_data/extraction_prompts.py',
             ROOT/'src/uteki/agents/runtime/deepseek_model.py', ROOT/'src/uteki/agents/runtime/call_costs.py',
             ROOT/'src/uteki/agents/runtime/model_factory.py', ROOT/'src/uteki/agents/runtime/run_budget.py')}})
    rows = []
    for repeat in (1, 2):
        for case in protocol['cases']:
            source = json.loads((prepared/'cases'/f'{case}.json').read_text())
            value = json.dumps(source, ensure_ascii=False, separators=(',', ':'))
            for arm in (protocol['arms'] if repeat == 1 else list(reversed(protocol['arms']))):
                folder = output/f'{case}-{arm}-{repeat}'
                folder.mkdir()
                prompt = (prepared/'prompts'/f'{arm}.txt').read_text()
                save(folder/'request.json', {'instructions': json_instructions(prompt, AgentOutputSchema(Extraction).json_schema()),
                     'input': source, 'provider': provider, 'model': model,
                     'max_tokens': protocol['max_tokens'], 'temperature': 0, 'thinking': 'disabled'})
                inner = model_adapter(model, provider)
                metered = MeteredModel(inner, folder/'calls', case, provider, model, pricing, budget)
                agent = Agent(name='DataExtractor', instructions=prompt, model=metered, output_type=Extraction,
                              model_settings=ModelSettings(max_tokens=protocol['max_tokens'], temperature=0))
                row = {'case': case, 'arm': arm, 'repeat': repeat, 'folder': folder.name}
                try:
                    result = await asyncio.wait_for(Runner.run(agent, value, max_turns=1,
                                                    run_config=RunConfig(tracing_disabled=True)), timeout=90)
                    data = result.final_output.model_dump(mode='json')
                    errors = validate_extraction(data, source['packet'])
                    save(folder/'output.json', data)
                    row.update(status='candidate' if not errors else 'invalid_evidence',
                               record_count=len(data['records']), validation_errors=errors,
                               semantic_review='pending')
                except BudgetExceeded:
                    row.update(status='budget_exhausted')
                except Exception as exc:
                    row.update(status='failed', error_type=type(exc).__name__,
                               http_status=getattr(exc, 'status_code', None))
                if inner.response_text is not None:
                    (folder/'raw-output.txt').write_text(inner.response_text)
                save(folder/'costs.json', summarize(folder/'calls'))
                save(folder/'result.json', row)
                rows.append(row)
                print(case, arm, repeat, row['status'], flush=True)
                if budget.summary()['unknown_requests'] or row['status'] == 'budget_exhausted':
                    final = {'status': 'stopped_unknown_cost' if budget.summary()['unknown_requests'] else 'stopped_budget',
                             'runs': rows, 'budget': budget.summary()}
                    save(output/'result.json', final)
                    return final
    final = {'status': 'completed_pending_review', 'runs': rows, 'budget': budget.summary(),
             'completed_at': datetime.now(timezone.utc).isoformat()}
    save(output/'result.json', final)
    return final


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('--output', type=Path, required=True)
    prep.add_argument('--candidate', type=Path, required=True)
    prep.add_argument('--upstream', type=Path, required=True)
    execute = commands.add_parser('run')
    execute.add_argument('--prepared', type=Path, required=True)
    execute.add_argument('--output', type=Path, required=True)
    execute.add_argument('--env-directory', type=Path, default=ROOT)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.output, args.candidate, args.upstream)
    else:
        load_provider_key(args.env_directory, 'deepseek')
        result = asyncio.run(run(args.prepared, args.output))
        raise SystemExit(0 if result['status'] == 'completed_pending_review' else 1)
