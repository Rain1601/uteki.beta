"""Deterministic earnings adapters. Source text is evidence, never instructions.

PDF coordinates refer to physical pages (1-based), not printed page numbers.
No OCR, translation, financial interpretation, or model calls.
"""
import hashlib
import re
from lxml import etree

VERSION = 'earnings-source-v0.1'


def digest(value):
    return hashlib.sha256(value).hexdigest()


def parse_transcript_xml(raw_xml):
    root = etree.fromstring(raw_xml, etree.XMLParser(resolve_entities=False, no_network=True))
    blocks = []
    speaker, role, turn, exchange = None, 'unknown', 0, None
    section, qa_number = 'prepared', 0
    diagnostics = []
    speaker_pattern = re.compile(r'^(Operator|[A-Z][^:]{1,110}(?:\)|Relations|Google)):\s*')
    for page_number, page in enumerate(root.findall('.//{*}page'), 1):
        for element in page.findall('.//{*}block'):
            text = ' '.join(' '.join(w.text or '' for w in line.findall('{*}word'))
                            for line in element.findall('{*}line')).strip()
            if not text:
                continue
            match = speaker_pattern.match(text)
            if match:
                speaker = match[1]
                role = ('operator' if speaker == 'Operator' else
                        'analyst' if re.search(r'\([^()]+\)$', speaker) else 'management')
                turn += 1
            if role == 'operator' and re.search(r'(?:first|next|last) question comes from', text, re.I):
                section = 'qa'
                qa_number += 1
                exchange = f'qa-{qa_number:02}'
            if role == 'operator' and 'concludes our question-and-answer' in text:
                section, exchange = 'closing', None
            if role == 'analyst' and section == 'prepared':
                diagnostics.append({'code': 'qa_boundary_fallback', 'message': 'Analyst before operator question cue; review boundary.'})
                section, qa_number, exchange = 'qa', 1, 'qa-01'
            ordinal = len(blocks) + 1
            blocks.append({
                'block_id': f'block-{ordinal:06}-{digest(text.encode())[:8]}',
                'ordinal': ordinal, 'type': 'paragraph', 'text': text,
                'text_hash': digest(text.encode()), 'source_anchor': None,
                'dom_path': None, 'reported_page': None, 'pdf_page': page_number,
                'bbox': [float(element.get(k)) for k in ('xMin','yMin','xMax','yMax')],
                'page_size': [float(page.get('width')), float(page.get('height'))],
                'speaker': speaker, 'speaker_role': role, 'turn_id': f'turn-{turn:03}',
                'section': section, 'exchange_id': exchange,
                'statement_status': 'source_statement_not_verified_fact',
                'style_signature': {}, 'table': None, 'asset_id': None, 'layout_role': None,
            })
    if not blocks or not qa_number or not any(b['section'] == 'closing' for b in blocks):
        raise ValueError('Incomplete transcript: expected opening, questions and closing')
    return blocks, diagnostics


def earnings_outline(blocks, document_id, source_sha, source_snapshot_id, form, title, diagnostics=(), parser_version=VERSION):
    def node(node_id, parent_id, kind, label, subset):
        return dict(node_id=node_id, parent_id=parent_id, kind=kind, title=label,
                    part_number=None, item_number=None, source_anchor=subset[0].get('source_anchor'),
                    reported_page=subset[0].get('reported_page'), pdf_page=subset[0].get('pdf_page'),
                    start_block_id=subset[0]['block_id'], end_block_id=subset[-1]['block_id'])
    nodes = [node('document', None, 'document', title, blocks)]
    if form == 'EARNINGS_CALL':
        for section, label in [('prepared','Management prepared remarks'),('qa','Analyst questions and answers'),('closing','Closing')]:
            subset = [b for b in blocks if b['section'] == section]
            if not subset:
                continue
            nodes.append(node(section, 'document', 'section', label, subset))
            key = 'exchange_id' if section == 'qa' else 'turn_id'
            for identity in dict.fromkeys(b[key] for b in subset):
                if not identity:
                    continue
                selected = [b for b in subset if b[key] == identity]
                speaker = next((b['speaker'] for b in selected if b['speaker_role'] == 'analyst'), selected[0]['speaker'])
                nodes.append(node(section + '-' + identity, section, 'exchange' if section == 'qa' else 'turn',
                                  (identity + ' · ' if section == 'qa' else '') + (speaker or 'Notice'), selected))
    else:
        # Explicit source headings only; no semantic inference of financial sections.
        starts = [0] + [i for i,b in enumerate(blocks) if i and b['type'] == 'heading_candidate']
        for n, start in enumerate(starts):
            end = starts[n+1] if n+1 < len(starts) else len(blocks)
            nodes.append(node(f'section-{n+1:03}', 'document', 'section', blocks[start]['text'][:140], blocks[start:end]))
    return dict(index_id='index-' + digest(f'{document_id}:{source_sha}:{parser_version}'.encode())[:20],
                schema_version='earnings-index-v0.1', parser_version=parser_version,
                source_snapshot_id=source_snapshot_id, form_type=form, nodes=nodes, diagnostics=list(diagnostics))
