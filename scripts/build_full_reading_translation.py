"""Assemble human-readable, page-aligned Codex translations without model calls.

The page registry reports presence, not semantic correctness. Publishing a PDF
requires all source pages; --allow-partial produces an explicitly partial draft.
"""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
from xml.sax.saxutils import escape

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'data/reading_library/alphabet'
TRANSLATIONS = LIB / 'translations/full-library'


def documents():
    return json.loads((LIB/'download_manifest.json').read_text())['documents']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refresh_registry():
    entries = []
    for doc in documents():
        if doc['status'] != 'downloaded':
            continue
        stem = Path(doc['path']).stem
        folder = TRANSLATIONS/stem
        present = [p for p in range(1, doc['pages']+1)
                   if (folder/'pages'/f'{p:03d}.md').exists()]
        missing = sorted(set(range(1, doc['pages']+1))-set(present))
        artifact = folder/'assembly.json'
        assembled = json.loads(artifact.read_text()) if artifact.exists() else None
        status = 'not_started' if not present else 'partial_translation'
        if not missing:
            status = 'all_pages_translated_pending_review'
        if assembled and assembled.get('visual_review') == 'passed':
            current = ROOT/assembled['output']
            valid = current.exists() and sha(current) == assembled['output_sha256']
            valid = valid and all(sha(folder/'pages'/f"{m['source_pdf_page']:03d}.md") == m['translation_sha256'] for m in assembled['mapping'])
            if valid and not missing:
                status = 'full_pdf_self_reviewed'
        entries.append({'document': stem, 'period': doc['period'], 'kind': doc['kind'],
                        'source_pages': doc['pages'], 'translated_pages': present,
                        'missing_pages': missing, 'status': status,
                        'source_url': doc['url'], 'source_sha256': doc['sha256'],
                        'assembly': assembled})
    total = sum(e['source_pages'] for e in entries)
    translated = sum(len(e['translated_pages']) for e in entries)
    registry = {'scope': '62 downloaded official Alphabet PDFs, FY2022-FY2025 and 2026 Q1/Q2',
                'method': 'Codex direct translation; no external LLM API',
                'source_pages': total, 'translated_pages': translated,
                'complete_library': all(not e['missing_pages'] for e in entries),
                'warning': 'File presence is not proof of translation quality; review remains separate.',
                'documents': entries}
    TRANSLATIONS.mkdir(parents=True, exist_ok=True)
    (TRANSLATIONS/'progress.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n')
    lines = ['# Alphabet 全量翻译进度', '',
             f'范围：已下载的 {len(entries)} 份官方 PDF，共 {total} 个来源页。',
             f'已落盘译文：{translated} 个来源页。此数字不是独立审校通过数量。', '',
             'Codex 直接全文翻译，不调用 AIHubMix。重复年报暂保留在清单，不未经逐页核验就认定可以省略。', '',
             '| 材料 | 已译 / 总页数 | 状态 |', '|---|---:|---|']
    names = {'not_started':'尚未开始','partial_translation':'部分已译',
             'all_pages_translated_pending_review':'全文译稿已落盘，待合并审核',
             'full_pdf_self_reviewed':'全文 PDF 已自校及排版检查，待独立人工审校'}
    for e in entries:
        label=e['document']
        if e['status']=='full_pdf_self_reviewed':
            label=f"[{label}](../../../../../{e['assembly']['output']})"
        lines.append(f"| {label} | {len(e['translated_pages'])} / {e['source_pages']} | {names[e['status']]} |")
    (TRANSLATIONS/'README.md').write_text('\n'.join(lines)+'\n')
    return registry


def import_first_batch():
    old = LIB/'translations/2025-10k/part-01-business/translation.md'
    parts = re.split(r'^## 原文第 (\d+) 页\s*$',old.read_text(),flags=re.M)
    destination = TRANSLATIONS/'alphabet-2025-Q4-10-K/pages'
    destination.mkdir(parents=True,exist_ok=True)
    for i in range(1,len(parts),2):
        printed = int(parts[i]); physical = printed+1
        target = destination/f'{physical:03d}.md'
        text = f'# PDF原文第 {physical} 页\n\n印刷页码：{printed}。\n\n'+parts[i+1].strip()+'\n'
        if not target.exists():
            target.write_text(text)


def build(stem, allow_partial=False, chinese_only=False):
    doc = next(d for d in documents() if Path(d['path']).stem == stem)
    source_path = LIB/doc['path']
    assert sha(source_path) == doc['sha256'], 'Source SHA changed'
    source = PdfReader(source_path)
    folder = TRANSLATIONS/stem
    page_files = [(n,folder/'pages'/f'{n:03d}.md') for n in range(1,len(source.pages)+1)]
    missing = [n for n,p in page_files if not p.exists()]
    if missing and not allow_partial:
        raise ValueError(f'Missing {len(missing)} pages: {missing}')
    page_files = [(n,p) for n,p in page_files if p.exists()]
    pdfmetrics.registerFont(TTFont('Reading','/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
    pdfmetrics.registerFontFamily('Reading',normal='Reading',bold='Reading',italic='Reading',boldItalic='Reading')
    # Filing-like reading layout: compact type and leading, with a narrower text
    # measure than tables.  The previous "report" rhythm was too airy relative to
    # SEC filings and often left a nearly blank continuation page.
    body = ParagraphStyle('body',fontName='Reading',fontSize=9.2,leading=13.2,
                          textColor=colors.HexColor('#253544'),wordWrap='CJK',
                          spaceAfter=4,leftIndent=27,rightIndent=27)
    head = ParagraphStyle('head',parent=body,fontSize=12.4,leading=16,
                          spaceBefore=7,spaceAfter=5,keepWithNext=True,
                          textColor=colors.HexColor('#235C66'))
    meta = ParagraphStyle('meta',parent=body,fontSize=7.4,leading=10.2,
                          textColor=colors.HexColor('#647583'))
    cell = ParagraphStyle('cell',parent=body,fontSize=7.45,leading=9.9,spaceAfter=0,
                          leftIndent=0,rightIndent=0)
    bullet = ParagraphStyle('bullet',parent=body,leftIndent=40,rightIndent=27,
                            firstLineIndent=-10,spaceAfter=3)
    nested = ParagraphStyle('nested',parent=bullet,leftIndent=53)
    def text(value,style=body):
        safe = escape(value)
        safe = re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',safe)
        return Paragraph(safe,style)
    edition = '中文阅读版' if chinese_only else '中英对照'
    def layout(story,label):
        stream = BytesIO()
        def frame(canvas,report):
            canvas.setFont('Reading',7.2); canvas.setFillColor(colors.HexColor('#647583'))
            canvas.drawString(52,777,stem+'  /  '+edition)
            canvas.drawRightString(560,777,label)
            canvas.setStrokeColor(colors.HexColor('#D7E2E4')); canvas.line(52,767,560,767)
            canvas.drawString(52,19,'非官方中文译文 · Codex 翻译与自校 · 英文原件为准')
            canvas.drawRightString(560,19,f'{label} · 译页 {report.page}')
        report = SimpleDocTemplate(stream,pagesize=(612,792),leftMargin=52,rightMargin=52,
                                   topMargin=36,bottomMargin=34)
        report.build(story,onFirstPage=frame,onLaterPages=frame)
        stream.seek(0)
        return PdfReader(stream)
    def markdown(md,page_path):
        lines=md.splitlines(); story=[]; i=0
        while i<len(lines):
            line=lines[i]; stripped=line.strip()
            if not stripped:
                i+=1; continue
            if line.startswith('# PDF原文第'):
                i+=1; continue
            illustration=re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)',stripped)
            if illustration:
                image_path=(page_path.parent/illustration.group(2)).resolve()
                if not image_path.is_relative_to(folder.resolve()):
                    raise ValueError('Illustration outside translation directory')
                graphic=Image(str(image_path))
                ratio=min(480/graphic.imageWidth,540/graphic.imageHeight)
                graphic.drawWidth=graphic.imageWidth*ratio
                graphic.drawHeight=graphic.imageHeight*ratio
                story.extend([text(illustration.group(1)+'（原图；中文图例见下文）',meta),graphic,Spacer(1,8)])
                i+=1;continue
            if stripped.startswith('|'):
                rows=[]
                while i<len(lines) and lines[i].strip().startswith('|'):
                    values=[c.strip() for c in lines[i].strip().strip('|').split('|')]
                    if not all(re.fullmatch(r'[:\- ]+',v or '-') for v in values):
                        rows.append(values)
                    i+=1
                cols=max(map(len,rows))
                rows=[r+['']*(cols-len(r)) for r in rows]
                # Give account descriptions room without squeezing numeric columns.
                numeric = cols>2 and all(sum(bool(re.search(r'\d',v)) for v in r[1:])>=cols-2 for r in rows[1:])
                # The frame reserves six points of padding on each side.
                widths=([198]+[310/(cols-1)]*(cols-1)) if numeric else ([508/cols]*cols)
                rendered=[[text(v,cell) for v in r] for r in rows]
                table=Table(rendered,colWidths=widths,repeatRows=1,hAlign='LEFT',splitByRow=1,splitInRow=1)
                table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#EDF3F4')),
                    ('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor('#B5C8CC')),
                    ('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#E0E8EA')),
                    ('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),
                    ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3)]))
                story.extend([table,Spacer(1,5)]); continue
            if stripped.startswith('#'):
                story.append(text(re.sub(r'^#+\s*','',stripped),head))
            elif stripped.startswith('- '):
                story.append(text('• '+stripped[2:],nested if line.startswith('  ') else bullet))
            else:
                story.append(text(stripped,meta if stripped.startswith('印刷页码') else body))
            i+=1
        return story
    writer=PdfWriter()
    title='完整逐页中文译稿' if not missing else '部分逐页中文译稿'
    cover=[Spacer(1,50),text('Alphabet',head),text(f"{doc['period']} · {doc['kind']}",head),
           text(title+' · '+edition,head),Spacer(1,20),
           text(f'本册包含 {len(page_files)} / {len(source.pages)} 个来源页的中文译文。'),
           text('中文译文按来源 PDF 页序连续排版。表格保留原始金额单位、列序与脚注。' if chinese_only
                else '每页英文原件后紧接中文译页。表格保留原始金额单位、列序与脚注；英文原件不重新排版。'),
           text('Codex 直接翻译并分段自校，未经独立人工审校，不是官方中文版本。全文覆盖不等于无误；发现问题请按 PDF 原文页码反馈。'),
           text('译稿正文中的“我们”均指公司；不加入投资分析。目录指向原文页码，PDF 书签可直接跳到原页或译文。'),
           text('官方来源',head),text(doc['url'],meta),
           text('来源 SHA-256：'+doc['sha256'],meta)]
    if missing:
        cover.append(text('尚未包含的来源页：'+', '.join(map(str,missing)),meta))
    writer.append(layout(cover,'阅读说明'),import_outline=False)
    writer.add_outline_item('阅读说明',0)
    mapping=[]
    for number,path in page_files:
        if chinese_only:
            cn=len(writer.pages)
            parent=writer.add_outline_item(f'PDF原文第 {number} 页 · 中文译文',cn)
        else:
            en=len(writer.pages)
            writer.add_page(source.pages[number-1])
            parent=writer.add_outline_item(f'PDF原文第 {number} 页',en)
            cn=len(writer.pages)
        writer.append(layout(markdown(path.read_text(),path),f'PDF原文第 {number} 页'),import_outline=False)
        if not chinese_only:
            writer.add_outline_item('中文译文',cn,parent=parent)
        row={'source_pdf_page':number,
             'chinese_pages':list(range(cn+1,len(writer.pages)+1)),
             'translation_sha256':sha(path)}
        if not chinese_only:
            row['english_page']=en+1
        mapping.append(row)
    output=ROOT/'output/pdf'/f"{stem}-{'zh' if chinese_only else 'zh-en'}.pdf"
    if missing:
        output=output.with_stem(output.stem+'-partial')
    output.parent.mkdir(parents=True,exist_ok=True)
    writer.add_metadata({'/Title':stem+' | '+title+' | '+edition,'/Author':'Codex; unofficial translation'})
    writer.write(output)
    # Mechanical retention check: source text and every translated cell/line.
    final=PdfReader(output); retained=0
    for m in mapping:
        if not chinese_only:
            assert source.pages[m['source_pdf_page']-1].extract_text()==final.pages[m['english_page']-1].extract_text()
        compact=lambda s:re.sub(r'\s+','',s)
        texts=[]
        for p in m['chinese_pages']:
            extracted=final.pages[p-1].extract_text()
            clean_lines=[line for line in extracted.splitlines()
                         if not line.startswith(stem+'  /')
                         and not line.startswith('非官方中文译文')
                         and not line.startswith('PDF原文第 ')]
            texts.append('\n'.join(clean_lines))
        cn=compact(''.join(texts))
        original=(folder/'pages'/f"{m['source_pdf_page']:03d}.md").read_text()
        for line in original.splitlines():
            if not line.strip() or line.startswith('# PDF原文第') or line.startswith('!['):continue
            values=line.strip().strip('|').split('|') if line.strip().startswith('|') else [line]
            for v in values:
                v=re.sub(r'^\s*(?:#+\s*|- )','',v.strip()).replace('**','')
                if not v or re.fullmatch(r'[:\- ]+',v):continue
                # Wide table cells can wrap across pages; PDF extraction may
                # interleave their numeric columns with the description. Check
                # every meaningful clause instead of incorrectly requiring the
                # original cell to be one contiguous extracted string.
                if line.strip().startswith('|') and len(compact(v))>60:
                    # Extremely long accounting-table labels are laid out in a
                    # narrow first column, so PDF text extraction changes their
                    # reading order. Their numbers remain mechanically checked;
                    # the full label is covered by visual review.
                    fragments=[compact(piece) for piece in re.findall(r'[\d$.,%]+',v)
                               if len(compact(piece))>=2]
                else:
                    fragments=[compact(piece) for piece in re.split(r'[，；：、（）()\s]+',v)]
                    fragments=[piece for piece in fragments if len(piece)>=4]
                if not fragments:
                    fragments=[compact(v)]
                for piece in fragments:
                    assert piece in cn,(m['source_pdf_page'],piece[:90])
                    retained+=1
    assembly={'source':doc['path'],'source_sha256':doc['sha256'],'edition':'chinese_only' if chinese_only else 'bilingual',
              'output':str(output.relative_to(ROOT)),'output_sha256':sha(output),
              'source_pages':len(source.pages),'covered_pages':len(page_files),
              'missing_pages':missing,'full_page_coverage':not missing,
              'output_pages':len(final.pages),'retained_text_units':retained,
              'visual_review':'pending','independent_human_review':'pending','mapping':mapping}
    (folder/('assembly-zh.json' if chinese_only else 'assembly.json')).write_text(json.dumps(assembly,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in assembly.items() if k!='mapping'},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--document');parser.add_argument('--import-first-batch',action='store_true')
    parser.add_argument('--allow-partial',action='store_true')
    parser.add_argument('--chinese-only',action='store_true')
    args=parser.parse_args()
    if args.import_first_batch:import_first_batch()
    if args.document:build(args.document,args.allow_partial,args.chinese_only)
    result=refresh_registry()
    print(f"Translation files: {result['translated_pages']} / {result['source_pages']} source pages")
