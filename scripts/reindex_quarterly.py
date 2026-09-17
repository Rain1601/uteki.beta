"""Offline, append-only quarterly index revision; sources are never changed."""
import hashlib
import json
from pathlib import Path
from uteki.infrastructure.document_sources.index_artifacts import build_index_artifacts

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'data/document_library/alphabet'


def main():
    path = LIB / 'catalog.json'
    original = path.read_bytes()
    catalog = json.loads(original)
    updates = []
    for doc in catalog['documents']:
        if doc['form'] not in {'10-Q', '10-Q/A'}:
            continue
        source = ROOT / doc['folder']
        output = source / 'indexes/v0.4-candidate'
        if output.exists():
            raise ValueError(f'Refusing to overwrite {output}')
        manifest = build_index_artifacts(source, output)
        index = json.loads((output / 'index.json').read_text())
        change = {'previous_index_folder': doc['index_folder'], 'index_id':manifest['index_id'],
                  'counts':manifest['counts'], 'diagnostics':index['diagnostics']}
        (output / 'CHANGELOG.md').write_text('# v0.4 Candidate / 候选索引\n\n'
            'Recursively unwrap layout/XBRL containers into paragraphs, headings and list items. Tables remain atomic. '
            'Mixed direct-text containers are conservatively retained; no semantic hierarchy or cross-page joining.\n\n'
            '递归展开布局及 XBRL 容器，保留段落、标题、列表和表格。混合直接文本的容器暂保守保留；不推断语义层级，不合并跨页段落。Block IDs change; old evidence remains on old indexes.\n\n'
            '```json\n' + json.dumps(change, ensure_ascii=False, indent=2) + '\n```\n', encoding='utf-8')
        doc.update(index_folder=str(output.relative_to(ROOT)), counts=manifest['counts'],status='indexed_candidate')
        updates.append({'document':doc['id'], **change})
    history = LIB / 'catalog_history'
    history.mkdir(exist_ok=True)
    (history / (hashlib.sha256(original).hexdigest()+'.json')).write_bytes(original)
    raw = (json.dumps(catalog, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()
    (history / (hashlib.sha256(raw).hexdigest()+'.json')).write_bytes(raw)
    path.write_bytes(raw)
    print(json.dumps(updates, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
