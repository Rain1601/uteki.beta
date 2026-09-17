"""Build a new immutable overlay collection from locally pinned indexes."""
import json
from pathlib import Path
from uteki.agents.document_reader import DocumentReader, sha
from uteki.agents.reading_groups import VERSION

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / 'experiments/reading_groups/v0.1'
out.mkdir(parents=True, exist_ok=False)
catalog = json.loads((ROOT / 'data/document_library/alphabet/catalog.json').read_text())
summary = []
for doc in catalog['documents']:
    if not doc.get('index_folder'):
        continue
    reader = DocumentReader(ROOT / doc['index_folder'])
    value = {'index_manifest': reader.manifest, 'version': VERSION,
             'rules_sha256': sha((ROOT / 'src/uteki/agents/reading_groups.py').read_bytes()),
             'groups': reader.groups}
    (out / (doc['id'] + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    summary.append({'document': doc['id'], 'groups': len(reader.groups)})
(out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary))
