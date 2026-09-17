"""Build a source-page-aligned reading PDF from a Codex-authored translation.

No network or model calls. Original source pages remain unchanged.
"""
from pathlib import Path
from io import BytesIO
import hashlib
import json
import re
from xml.sax.saxutils import escape

from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / 'data/reading_library/alphabet'
BATCH = LIBRARY / 'translations/2025-10k/part-01-business'
SOURCE = LIBRARY / 'originals/2025/alphabet-2025-Q4-10-K.pdf'
OUTPUT = ROOT / 'output/pdf/alphabet-2025-10k-part01-business-zh-en.pdf'
URL = 'https://s206.q4cdn.com/479360582/files/doc_financials/2025/q4/GOOG-10-K-2025.pdf'
FONT = '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'


def main():
    pdfmetrics.registerFont(TTFont('Reading', FONT))
    body = ParagraphStyle('body', fontName='Reading', fontSize=11, leading=18,
                          textColor=HexColor('#263343'), wordWrap='CJK', spaceAfter=9)
    heading = ParagraphStyle('heading', parent=body, fontSize=14, leading=22,
                             textColor=HexColor('#235C66'), spaceBefore=12,
                             spaceAfter=9, keepWithNext=True)
    title = ParagraphStyle('title', parent=heading, fontSize=25, leading=36)
    meta = ParagraphStyle('meta', parent=body, fontSize=9, leading=15,
                          textColor=HexColor('#667684'))
    bullet = ParagraphStyle('bullet', parent=body, leftIndent=13, firstLineIndent=-10)
    nested = ParagraphStyle('nested', parent=bullet, leftIndent=27)

    def make_pdf(story, label):
        stream = BytesIO()
        def frame(canvas, doc):
            canvas.setFont('Reading', 8)
            canvas.setFillColor(HexColor('#667684'))
            canvas.drawString(48, 762, 'ALPHABET  /  FY2025 10-K  /  中英对照')
            canvas.drawRightString(564, 762, label)
            canvas.setStrokeColor(HexColor('#D7E2E4'))
            canvas.line(48, 750, 564, 750)
            canvas.drawString(48, 29, '非官方中文译文 · Codex 翻译与自校 · 英文原件为准')
            canvas.drawRightString(564, 29, f'{label} · 译页 {doc.page}')
        doc = SimpleDocTemplate(stream, pagesize=(612, 792), rightMargin=48,
                                leftMargin=48, topMargin=57, bottomMargin=53)
        doc.build(story, onFirstPage=frame, onLaterPages=frame)
        stream.seek(0)
        return PdfReader(stream)

    def para(text, style=body):
        return Paragraph(escape(text), style)

    content = (BATCH / 'translation.md').read_text()
    parts = re.split(r'^## 原文第 (\d+) 页\s*$', content, flags=re.M)
    source = PdfReader(SOURCE)
    writer = PdfWriter()
    cover = [Spacer(1, 64), para('Alphabet', title),
             para('2025 年度报告', title), para('业务章节 · 中英逐页对照', heading),
             Spacer(1, 24), para('第一批  /  原文印刷页 3-8'),
             para('前瞻性声明与完整的第 1 项“业务”'), Spacer(1, 22),
             para('阅读方式', heading),
             para('每张英文原页之后，紧接该页的中文译文。中文为便于阅读可能排成多页；页眉始终标明所对应的原文页码。英文页直接取自官方 PDF，未重新排版。'),
             para('译文范围与状态', heading),
             para('本册覆盖原 PDF 第 4-9 页，共 6 个来源页。它不是整份 99 页年报的完整译本；封面、目录、风险因素及后续章节尚不在本批中。'),
             para('由 Codex 直接翻译并对照自校，未经独立人工审校。正文保持公司口吻，不加入投资分析。产品名及财务报告分部名称保留英文，以便查找与核对。'),
             para('官方原件', heading), para(URL, meta)]
    writer.append(make_pdf(cover, '阅读说明'), import_outline=False)
    writer.add_outline_item('阅读说明', 0)
    mapping = []
    for i in range(1, len(parts), 2):
        printed = int(parts[i])
        story = []
        for raw in parts[i+1].split('\n\n'):
            raw = raw.strip('\n')
            if not raw.strip():
                continue
            if raw.startswith('### '):
                story.append(para(raw[4:].strip(), heading))
            elif raw.lstrip().startswith('- '):
                for line in raw.splitlines():
                    if not line.strip():
                        continue
                    deep = line.startswith('  ')
                    story.append(para('• ' + line.strip()[2:], nested if deep else bullet))
            else:
                story.append(para(raw.strip()))
        english_at = len(writer.pages)
        writer.add_page(source.pages[printed])
        parent = writer.add_outline_item(f'原文第 {printed} 页', english_at)
        chinese_at = len(writer.pages)
        translated = make_pdf(story, f'原文第 {printed} 页')
        writer.append(translated, import_outline=False)
        writer.add_outline_item('中文译文', chinese_at, parent=parent)
        mapping.append({'printed_page': printed, 'source_pdf_page': printed+1,
                        'output_english_page': english_at+1,
                        'output_chinese_pages': list(range(chinese_at+1, len(writer.pages)+1))})
    writer.add_metadata({'/Title': 'Alphabet FY2025 10-K | Business | 中英对照',
                         '/Author': 'Codex - unofficial translation',
                         '/Subject': 'Source printed pages 3-8; not the full annual report'})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    writer.write(OUTPUT)
    manifest = {'batch': '2025-10k-part01-business', 'version': 'v0.1',
                'source_url': URL, 'source_file': str(SOURCE.relative_to(ROOT)),
                'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                'translation_sha256': hashlib.sha256((BATCH/'translation.md').read_bytes()).hexdigest(),
                'output_file': str(OUTPUT.relative_to(ROOT)),
                'output_sha256': hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
                'source_total_pages': len(source.pages), 'covered_source_pages': 6,
                'output_pages': len(writer.pages), 'mapping': mapping,
                'method': 'Codex direct translation; no provider API calls',
                'review': 'Codex self-review completed; independent human review pending',
                'complete_document': False}
    (BATCH/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
