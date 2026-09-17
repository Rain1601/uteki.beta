"""Import immutable real experiments as unaccepted research candidates."""
import copy
from collections import Counter
import hashlib
import json
from pathlib import Path


def import_rows(root):
    root = Path(root)
    rows = []
    for manifest_path in sorted((root/'experiments/analysis_comparison').glob('open-drivers-*/manifest.json')):
        manifest = json.loads(manifest_path.read_text())
        documents = {d['id']: d for d in manifest['documents']}
        for case, question in manifest['cases'].items():
            for mode in ('single', 'team'):
                folder = manifest_path.parent/case/mode
                path = folder/'result.json'
                if not path.exists():
                    continue
                result = json.loads(path.read_text())
                reads = Counter()
                for tool in folder.glob('tool-*.json'):
                    record = json.loads(tool.read_text())
                    if record['tool'] == 'read' and record['result'].get('blocks'):
                        reads[record['result']['document_id']] += 1
                if not reads:
                    continue
                primary = documents[reads.most_common(1)[0][0]]
                answer = copy.deepcopy(result['answer'])
                for claim in answer.get('claims', []):
                    for citation in claim.get('citations', []):
                        doc = documents.get(citation['document_id'])
                        if doc:
                            version = Path(doc['index_folder']).name
                            # The existing index route is retained as a precise document-version entrance.
                            citation['url'] = f"/companies/alphabet/documents/{doc['accession']}/indexes/{version}/source#{citation['block_id']}"
                            citation['source_url'] = doc['source_url']
                relative = str(path.relative_to(root))
                identifier = 'research-' + hashlib.sha256(relative.encode()).hexdigest()[:16]
                cost = json.loads((folder/'costs.json').read_text()) if (folder/'costs.json').exists() else {}
                # These two inspected experiments share analyst -> reviewer -> revision
                # topology. Unknown future teams must declare identity explicitly.
                known = manifest_path.parent.name in {'open-drivers-gpt54mini-v0.1', 'open-drivers-gpt54mini-v0.2'}
                researcher = manifest.get('researchers', {}).get(mode) or ({
                    'id': 'single-default' if mode == 'single' else 'team-a',
                    'label': 'Single Agent' if mode == 'single' else 'Team A',
                } if known else {'id': 'unassigned', 'label': '待归类 / Unassigned'})
                rows.append({
                    'id': identifier, 'company_id': 'alphabet', 'scope': 'company-drivers',
                    'researcher_id': researcher['id'], 'researcher_label': researcher['label'],
                    'config_version': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                    'config_source': str(manifest_path.relative_to(root)),
                    'primary_document_id': primary['id'], 'primary_title': primary['title'],
                    'primary_inferred': True,
                    'primary_note': '历史运行未声明主材料；按成功读取次数推定，采纳前需确认。',
                    'material_available_at': primary['filed_at']+'T00:00:00+00:00',
                    'material_time_precision': 'date',
                    'knowledge_cutoff_at': max(d['filed_at'] for d in documents.values())+'T23:59:59+00:00',
                    'run_started_at': manifest['created_at'],
                    'available_at': manifest['created_at'],
                    'run_id': relative, 'mode': mode, 'question': question,
                    'title': manifest_path.parent.name + ' · ' + mode,
                    'answer': answer, 'validation_status': 'passed' if not result['citation_errors'] else 'failed',
                    'citation_errors': result['citation_errors'],
                    'experiment_url': '/experiments/'+manifest_path.parent.name+'/review.html',
                    'source_url': primary['source_url'],
                    'source_result_path': relative,
                    'source_result_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                    'source_manifest_path': str(manifest_path.relative_to(root)),
                    'status': 'candidate', 'revision': 1,
                    'comments': [], 'baseline_snapshot_id': None,
                    'elapsed_seconds': result['elapsed_seconds'],
                    'estimated_usd': cost.get('known_estimated_usd'),
                    'context_note': '历史独立实验；无继承基线。引用通过不表示论证正确。',
                })
    return rows
