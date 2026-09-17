"""Collect publicly filed originals, with an explicit per-document failure ledger."""
import gzip
import hashlib
import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from lxml import html
from uteki.infrastructure.document_sources.index_artifacts import build_index_artifacts

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'data/document_library/alphabet'
UA = os.environ.get('SEC_USER_AGENT', 'Uteki/0.1 personal financial document research')


def get(url):
    time.sleep(.6)
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=35) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        body = error.read()
        diagnostic = {'url':url,'status':error.code,'body':body.decode('utf-8', errors='replace')[:12000]}
        write(LIB / 'download_diagnostics' / (hashlib.sha256(js(diagnostic)).hexdigest() + '.json'), js(diagnostic))
        raise


def write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError('immutable file conflict: ' + str(path))
    else:
        path.write_bytes(raw)


def js(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def rows(data):
    return [dict(zip(data, values)) for values in zip(*data.values())]


def filings(cik):
    url = f'https://data.sec.gov/submissions/CIK{cik:010}.json'
    raw = get(url)
    now = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    write(LIB / 'discovery' / f'{cik}-{now}.json', raw)
    data = json.loads(raw)
    result = rows(data['filings']['recent'])
    for older in data['filings']['files']:
        if older['filingTo'] >= '2022-01-01':
            result += rows(json.loads(get('https://data.sec.gov/submissions/' + older['name'])))
            time.sleep(.25)
    return result


def collect(item):
    item = dict(item)
    try:
        if item['id'] == 'alphabet-000165204426000018':
            folder = ROOT / 'data/source_documents/alphabet_2025_10k'
            item.update(folder=str(folder.relative_to(ROOT)), index_folder=str((folder / 'indexes/v0.1').relative_to(ROOT)), status='indexed_frozen')
            return item
        folder = LIB / 'sources' / item['id']
        source = folder / 'source.html.gz'
        raw = gzip.decompress(source.read_bytes()) if source.exists() else get(item['source_url'])
        tree = html.document_fromstring(raw)
        if len(raw) < 2000 or 'access denied' in tree.text_content()[:300].lower():
            raise ValueError('invalid source body')
        sha = hashlib.sha256(raw).hexdigest()
        write(source, gzip.compress(raw, mtime=0))
        manifest = {'document_id': item['id'], 'source_snapshot_id': item['id'] + '-' + sha[:8],
                    'source_url': item['source_url'], 'content_sha256': sha, 'form': item['form'],
                    'filed_at': item['filed_at'], 'period_end': item['period_end']}
        write(folder / 'manifest.json', js(manifest))
        item.update(folder=str(folder.relative_to(ROOT)), status='downloaded', sha256=sha)
        asset_errors = []
        for img in tree.xpath('//img[@src]'):
            try:
                asset_url = urljoin(item['source_url'], img.get('src'))
                target = folder / 'assets' / Path(img.get('src')).name
                if not target.exists():
                    write(target, get(asset_url))
            except Exception as e:
                asset_errors.append(type(e).__name__)
        if item['category'] == 'filing':
            try:
                version = 'v0.4-candidate' if item['form'] in ('10-Q','10-Q/A') else 'v0.1-candidate'
                out = folder / 'indexes' / version
                if (out / 'manifest.json').exists():
                    index_manifest = json.loads((out / 'manifest.json').read_text())
                else:
                    index_manifest = build_index_artifacts(folder, out)
                item.update(index_folder=str(out.relative_to(ROOT)), status='indexed_candidate', counts=index_manifest['counts'])
            except Exception as e:
                item['index_error'] = type(e).__name__ + ': ' + str(e)[:180]
        if asset_errors:
            item['asset_errors'] = asset_errors
    except Exception as e:
        item.update(status='download_failed', error=type(e).__name__ + ': ' + str(e)[:160])
    print(item['id'], item['status'], flush=True)
    return item


def main():
    all_rows = filings(1652044)
    selected = [r for r in all_rows if r['form'] in ('10-K','10-Q','10-K/A','10-Q/A') and
                '2022' <= r.get('reportDate','')[:4] <= '2026']
    items = []
    for r in selected:
        acc = r['accessionNumber'].replace('-','')
        items.append({'id':'alphabet-' + acc, 'company_id':'alphabet', 'category':'filing', 'form':r['form'],
                      'period_end':r['reportDate'], 'filed_at':r['filingDate'], 'accession':r['accessionNumber'],
                      'title':f"Alphabet {r['reportDate']} {r['form']}",
                      'source_url':f"https://www.sec.gov/Archives/edgar/data/1652044/{acc}/{r['primaryDocument']}",
                      'discovery_source':'https://data.sec.gov/submissions/CIK0001652044.json'})
    docs = [collect(item) for item in items]
    catalog = {'company_id':'alphabet','requested_source':'https://abc.xyz/investor/Earnings/default.aspx',
               'collected_at':datetime.now(timezone.utc).isoformat(), 'year_basis':'report period year',
               'scope_years':[2022,2023,2024,2025,2026], 'documents':docs,
               'notes':['SEC original filings used because local connection to abc.xyz failed.',
                        'Candidate indexes are not human-approved; downloaded does not mean semantically extracted.']}
    LIB.mkdir(parents=True,exist_ok=True)
    # Catalog is a current pointer; immutable sources and discovery records are retained.
    write(LIB / 'catalog_history' / (hashlib.sha256(js(catalog)).hexdigest() + '.json'), js(catalog))
    (LIB / 'catalog.json').write_bytes(js(catalog))
    print('CATALOG',len(docs),{s:sum(d['status']==s for d in docs) for s in set(d['status'] for d in docs)},flush=True)


if __name__ == '__main__':
    main()
