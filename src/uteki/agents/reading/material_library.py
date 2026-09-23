"""Unified discovery and immutable, date-bounded material manifests."""
import json
from datetime import date
from pathlib import Path
from uteki.agents.reading.document_reader import DocumentReader


def load_catalog(root):
    folder = Path(root)/'data/document_library/alphabet'
    catalog = json.loads((folder/'catalog.json').read_text())
    extra = folder/'earnings.json'
    if extra.exists():
        catalog['documents'] += json.loads(extra.read_text())['documents']
    ids = [d['id'] for d in catalog['documents']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate material identity')
    return catalog


def pin_materials(root, cutoff, document_ids):
    """Date-level only: includes material publicly dated on/before cutoff.

    Transcript availability uses event date as a disclosed approximation; not an
    independently verified point-in-time dataset for financial backtesting.
    """
    date.fromisoformat(cutoff)
    docs = {d['id']:d for d in load_catalog(root)['documents']}
    selected = []
    for identity in dict.fromkeys(document_ids):
        d = docs[identity]
        published = d.get('published_at') or d.get('filed_at')
        if not published or date.fromisoformat(published) > date.fromisoformat(cutoff):
            raise ValueError('Material after cutoff or publication date unknown: ' + identity)
        if not d.get('index_folder'):
            raise ValueError('Material is not indexed: ' + identity)
        selected.append(d)
    return {'documents':selected,'indexes':{d['id']:DocumentReader(Path(root)/d['index_folder']).manifest for d in selected},
            'material_cutoff':cutoff,'cutoff_precision':'date',
            'availability_caveat':'Transcript event date is not verified upload time; not a blind historical backtest.'}
