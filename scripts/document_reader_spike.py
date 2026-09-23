"""A local JSON tool adapter usable by Codex; not an autonomous model runner."""
import argparse
import gzip
import json
from pathlib import Path
from lxml import html
from uteki.agents.reading.document_reader import DocumentReader, sha

ROOT = Path(__file__).resolve().parents[1]


def reader_hash():
    return sha(Path(__file__).read_bytes() + (ROOT / 'src/uteki/agents/reading/document_reader.py').read_bytes()
               + (ROOT / 'src/uteki/agents/reading/reading_groups.py').read_bytes())


def write_new(path, value):
    with path.open('x') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('tool', choices=['init', 'outline', 'search', 'read'])
    parser.add_argument('--arguments', default='{}')
    args = parser.parse_args()
    params = json.loads(args.arguments)
    if args.tool == 'init':
        catalog = json.loads((ROOT / 'data/document_library/alphabet/catalog.json').read_text())
        doc = next(d for d in catalog['documents'] if d['id'] == params['document_id'])
        reader = DocumentReader(ROOT / doc['index_folder'])
        raw = gzip.decompress((ROOT / doc['folder'] / 'source.html.gz').read_bytes())
        if sha(raw) != reader.manifest['source_sha256']:
            raise ValueError('Source hash mismatch')
        args.run.mkdir(parents=True, exist_ok=False)
        write_new(args.run / 'manifest.json', {'question': params['question'], 'document': doc,
                  'index_manifest': reader.manifest, 'reader_sha256': reader_hash(),
                  'mode': 'Codex-directed demonstration; not blind evaluation', 'review_status': 'pending'})
        # A separate review copy: source snapshot remains byte-for-byte untouched.
        tree = html.fromstring(raw, parser=html.HTMLParser(encoding='utf-8'))
        meta = html.Element('meta', charset='utf-8')
        tree.find('head').insert(0, meta)
        paths = {tree.getroottree().getpath(el): el for el in tree.iter()}
        for block in reader.blocks:
            target = paths.get(block['dom_path'])
            if target is not None and target.getparent() is not None:
                marker = html.Element('span', id=block['block_id'])
                marker.set('class', 'reader-evidence-marker')
                target.addprevious(marker)
        style = html.Element('style')
        style.text = '.reader-evidence-marker:target + * {outline:3px solid #d3a600;background:#fff5c2;scroll-margin-top:40px}'
        tree.append(style)
        (args.run / 'source.html').write_bytes(html.tostring(tree, encoding='utf-8', include_meta_content_type=True))
        write_new(args.run / 'ready.json', {'ready': True})
        print(json.dumps({'run': str(args.run), 'status': 'initialized'}))
        return
    if not (args.run / 'ready.json').exists():
        raise ValueError('Initialization incomplete; create a new run')
    manifest = json.loads((args.run / 'manifest.json').read_text())
    reader = DocumentReader(ROOT / manifest['document']['index_folder'])
    if reader.manifest != manifest['index_manifest']:
        raise ValueError('Pinned index changed')
    if reader_hash() != manifest['reader_sha256']:
        raise ValueError('Reader changed; create a new run')
    result = getattr(reader, args.tool)(**params)
    number = len(list(args.run.glob('call-*.json'))) + 1
    write_new(args.run / f'call-{number:03}.json', {'tool': args.tool, 'arguments': params,
              'result': result, 'result_bytes': len(json.dumps(result).encode())})
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
