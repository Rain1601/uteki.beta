"""Render every PDF page for inspection and check translated text bounds."""
import argparse,hashlib,json,subprocess
from pathlib import Path
import pdfplumber
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('document');parser.add_argument('--chinese-only',action='store_true');args=parser.parse_args()
folder=ROOT/'data/reading_library/alphabet/translations/full-library'/args.document
assembly=json.loads((folder/('assembly-zh.json' if args.chinese_only else 'assembly.json')).read_text())
pdf=pdfplumber.open(ROOT/assembly['output'])
out=ROOT/'tmp/pdfs'/(args.document+'-zh' if args.chinese_only else args.document)
out.mkdir(parents=True,exist_ok=True)
# A rebuilt PDF can have fewer pages. Remove only this document's stale render
# outputs before counting the fresh render set, otherwise old PNGs make the
# page-count assertion fail and can contaminate visual review.
for stale in out.glob('render-*.png'):
    stale.unlink()
for stale in out.glob('sheet-*.jpg'):
    stale.unlink()
chinese={p for row in assembly['mapping'] for p in row['chinese_pages']}
findings=[];thumbs=[]
subprocess.run(['pdftoppm','-scale-to','1050','-png',str(ROOT/assembly['output']),str(out/'render')],check=True)
renders=sorted(out.glob('render-*.png'))
assert len(renders)==len(pdf.pages)
for number,page in enumerate(pdf.pages,1):
    if number in chinese:
        for block in page.chars:
            x0,y0,x1,y1=block['x0'],block['top'],block['x1'],block['bottom']
            # The running header/footer intentionally sit outside the content
            # frame. Validate translated content only, not those decorations.
            if 30 <= y0 and y1 <= 755 and (x0<50 or x1>563):
                findings.append({'page':number,'bbox':[x0,y0,x1,y1],'text':block['text']})
    # Full-size rendered pages remain available for per-page drill-down.
    full=renders[number-1]
    im=Image.open(full);im.thumbnail((240,310))
    tile=Image.new('RGB',(260,340),'#edf1f4');tile.paste(im,((260-im.width)//2,23))
    ImageDraw.Draw(tile).text((10,5),f'PDF {number} '+('ZH' if number in chinese else 'EN / COVER'),fill='#172b38')
    thumbs.append(tile)
for offset in range(0,len(thumbs),16):
    group=thumbs[offset:offset+16]
    sheet=Image.new('RGB',(1040,340*((len(group)+3)//4)),'white')
    for i,tile in enumerate(group):sheet.paste(tile,((i%4)*260,(i//4)*340))
    sheet.save(out/f'sheet-{offset//16+1:02d}.jpg',quality=88)
result={'output_sha256':hashlib.sha256((ROOT/assembly['output']).read_bytes()).hexdigest(),
        'pages_rendered':len(pdf.pages),'translated_pages_checked':len(chinese),
        'bounds_findings':findings,'visual_review':'pending inspection of contact sheets and full-size samples'}
(out/'qa.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
