"""Ingest already downloaded official originals; no network or LLM calls.

Usage: PYTHONPATH=src:. .venv/bin/python scripts/ingest_earnings_q425.py
Requires Poppler. Source copies and indexes are immutable; repeat is a no-op.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import re
import subprocess
import tempfile

from uteki.infrastructure.document_sources.earnings import digest, parse_transcript_xml, earnings_outline
from uteki.infrastructure.document_sources.sec_index import parse_sec_source
from uteki.infrastructure.document_sources.index_artifacts import _block_payload

ROOT = Path(__file__).resolve().parents[1]
CALL_PAGE = 'https://abc.xyz/investor/events/event-details/2026/2025-Q4-Earnings-Call-2026-Dr_C033hS6/default.aspx'
CALL_PDF = 'https://s206.q4cdn.com/479360582/files/doc_events/2026/Feb/04/2025_Q4_Earnings_Transcript.pdf'
RELEASE = 'https://www.sec.gov/Archives/edgar/data/1652044/000165204426000012/googexhibit991q42025.htm'


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)+'\n').encode()


def immutable(path, raw):
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError(f'Immutable artifact differs: {path}; create a new version')
    else:
        with path.open('xb') as stream:
            stream.write(raw)


def ingest(root, path, kind):
    raw = path.read_bytes()
    source_sha = digest(raw)
    identity = 'alphabet-2025q4-' + kind
    source = root / 'data/document_library/alphabet/sources' / identity
    source.mkdir(parents=True, exist_ok=True)
    is_call = kind == 'call'
    form = 'EARNINGS_CALL' if is_call else 'EARNINGS_RELEASE'
    title = 'Alphabet 2025 Q4 ' + ('Earnings call' if is_call else 'Earnings release')
    url = CALL_PDF if is_call else RELEASE
    filename = 'source.pdf' if is_call else 'source.original'
    immutable(source/filename, raw)
    source_snapshot_id = identity + '-' + source_sha[:12]
    source_manifest = source/'manifest.json'
    if not source_manifest.exists():
        immutable(source_manifest, encoded(dict(document_id=identity, source_snapshot_id=source_snapshot_id,
            source_url=url, discovery_source=CALL_PAGE if is_call else RELEASE,
            content_sha256=source_sha, mime_type='application/pdf' if is_call else 'text/html',
            acquired_at=datetime.now(timezone.utc).isoformat(), period_end='2025-12-31',
            published_at='2026-02-04', publication_precision='date', form=form,
            publication_note='Event/release date; transcript upload timestamp not independently verified. Use date-level cutoffs only.')))
    index_folder = source/('indexes/v0.1-candidate' if is_call else 'indexes/v0.2-candidate')
    if (index_folder/'manifest.json').exists():
        manifest = json.loads((index_folder/'manifest.json').read_text())
        if manifest['source_sha256'] != source_sha:
            raise ValueError('Source changed; use a new source snapshot')
    else:
        index_folder.mkdir(parents=True, exist_ok=True)
        if is_call:
            with tempfile.TemporaryDirectory(prefix='uteki-earnings-') as temp:
                xml = Path(temp)/'layout.xml'
                subprocess.run(['pdftotext','-bbox-layout',str(source/filename),str(xml)],check=True)
                xml_raw = xml.read_bytes()
            immutable(source/'layout.xml', xml_raw)
            blocks, diagnostics = parse_transcript_xml(xml_raw)
            assets_dir = source/'assets'
            assets_dir.mkdir(exist_ok=True)
            subprocess.run(['pdftoppm','-jpeg','-r','110',str(source/filename),str(assets_dir/'page')],check=True)
            assets = [{'filename': p.name, 'source_path':p.name, 'sha256':digest(p.read_bytes()),
                       'pdf_page':int(p.stem.split('-')[-1]), 'mime_type':'image/jpeg'}
                      for p in sorted(assets_dir.glob('page-*.jpg'))]
        else:
            # Preserve SEC SGML envelope separately; the inner HTML is a derived view.
            match = re.search(br'<html\b.*?</html>', raw, re.I|re.S)
            if not match:
                raise ValueError('Release has no HTML document')
            inner = match[0]
            immutable(source/'source.html.gz', gzip.compress(inner,mtime=0))
            parsed = parse_sec_source(identity,url,inner,source_snapshot_id=source_snapshot_id,
                                      form_type=form,parser_version='sec-source-blocks-v0.1.5')
            if parsed.assets:
                raise ValueError('Release images require acquisition before indexing')
            blocks = [_block_payload(b) for b in parsed.blocks]
            # First release page has no printed footer: the SEC backfill heuristic
            # incorrectly borrows the next page's number. Do not expose it as fact.
            for block in blocks:
                block['parser_page_hint'] = block['reported_page']
                block['reported_page'] = int(block['text']) if block['type']=='page_marker' and block['text'].isdigit() else None
            diagnostics = [{'code':'release_page_mapping_unverified','severity':'warning',
                'message':'Printed footers retained, but paragraph-to-page mapping is unverified. Use exact DOM locations, not inferred page numbers.'}]
            assets = []
        index = earnings_outline(blocks,identity,source_sha,source_snapshot_id,form,title,diagnostics,
                                 parser_version='earnings-source-v0.1' if is_call else 'earnings-release-v0.2')
        artifacts = {'index.json':encoded(index),'assets.json':encoded({'assets':assets}),
                     'blocks.jsonl':b''.join(json.dumps(b,ensure_ascii=False,sort_keys=True).encode()+b'\n' for b in blocks)}
        for name, value in artifacts.items():
            immutable(index_folder/name,value)
        manifest = dict(index_id=index['index_id'],index_version=index_folder.name,status='candidate',
            schema_version=index['schema_version'],parser_version=index['parser_version'],
            source_snapshot_id=source_snapshot_id,source_sha256=source_sha,form_type=form,
            counts={'blocks':len(blocks),'tables':sum(b['type']=='table' for b in blocks),
                    'pages':max((b.get('pdf_page',0) for b in blocks),default=0) if is_call else None,
                    'exchanges':sum(n['kind']=='exchange' for n in index['nodes']), 'diagnostics':len(diagnostics)},
            artifacts={name:{'sha256':digest(value),'bytes':len(value)} for name,value in artifacts.items()},
            extraction_runtime=subprocess.run(['pdftotext','-v'],capture_output=True,text=True).stderr.strip() if is_call else 'lxml SEC DOM adapter')
        immutable(index_folder/'manifest.json',encoded(manifest))
        immutable(index_folder/'CHANGELOG.md',('# '+index_folder.name+'\n\nOfficial source ingestion; deterministic blocks and source locators.\nNo LLM/OCR/translation. Human review pending.\nPublication date is event date, not verified transcript upload time.\n'+('' if is_call else 'v0.2: remove unreliable paragraph page numbers; retain printed footer text and exact DOM locators. v0.1 is superseded, not deleted.\n')).encode())
    return dict(id=identity,accession=identity,company_id='alphabet',category='earnings',form=form,
                title=title,period_end='2025-12-31',filed_at='2026-02-04',published_at='2026-02-04',
                publication_precision='date',source_url=url,discovery_source=CALL_PAGE if is_call else RELEASE,
                folder=str(source.relative_to(root)),index_folder=str(index_folder.relative_to(root)),
                sha256=source_sha,status='indexed_candidate',source_format='pdf' if is_call else 'html',
                counts=manifest['counts'])


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--call',type=Path,default=Path('/tmp/uteki-q425-call.pdf'))
    parser.add_argument('--release',type=Path,default=Path('/tmp/uteki-q425-release.html'))
    args=parser.parse_args()
    docs=[ingest(ROOT,args.call,'call'),ingest(ROOT,args.release,'release')]
    catalog=ROOT/'data/document_library/alphabet/earnings.json'
    value=encoded({'company_id':'alphabet','documents':docs,
        'gaps':['2025 Q4 investor slides: not yet verified/acquired; do not assume available',
                'Other quarters and competitor calls not acquired']})
    if catalog.exists() and catalog.read_bytes()!=value:
        old=catalog.read_bytes()
        immutable(catalog.with_suffix('.'+digest(old)[:12]+'.bak'),old)
        with tempfile.NamedTemporaryFile(dir=catalog.parent,delete=False) as stream:
            stream.write(value)
            pending=Path(stream.name)
        pending.replace(catalog)
    else:
        immutable(catalog,value)
    print(json.dumps([{k:d[k] for k in ('id','status','counts')} for d in docs],indent=2))


if __name__=='__main__':
    main()
