"""Explicit document/version routing; never resolve a URL as a filesystem path."""
from pathlib import Path
import json


def index_url(doc):
    version = Path(doc.get('index_folder', 'v0.1-candidate')).name
    return f"/companies/{doc['company_id']}/documents/{doc['accession']}/indexes/{version}"


def resolve_index(path, catalog, root):
    versions = []
    for current in catalog['documents']:
        if not current.get('index_folder'):
            continue
        folder = (root / current['index_folder']).resolve()
        if not folder.is_relative_to(root.resolve()):
            raise ValueError('Index outside registry root')
        for manifest_path in folder.parent.glob('*/manifest.json'):
            manifest = json.loads(manifest_path.read_text())
            versions.append(dict(current, index_folder=str(manifest_path.parent.relative_to(root.resolve())),
                status='indexed_frozen' if manifest['status']=='frozen' else 'indexed_candidate'))
    for doc in versions:
        if not doc.get('index_folder') or not doc['status'].startswith('indexed'):
            continue
        base = index_url(doc)
        if path == base or path.startswith(base + '/'):
            source = (root / doc['folder']).resolve()
            index = (root / doc['index_folder']).resolve()
            if not source.is_relative_to(root.resolve()) or not index.is_relative_to(source):
                raise ValueError('Document registry points outside source directory')
            return doc, source, index, path[len(base):], base
    return None
