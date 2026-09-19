"""Small escaped report renderer and readable text diffs. Raw HTML is never run."""
from difflib import SequenceMatcher
from html import escape
import re
from urllib.parse import urlsplit


def inline(text):
    parts, offset = [], 0
    for match in re.finditer(r'\[([^\]]+)\]\(([^\s)]+)\)', text):
        parts.append(escape(text[offset:match.start()]))
        label, href = match.groups()
        parsed = urlsplit(href)
        if parsed.scheme in {'http', 'https'} or (href.startswith('/companies/') and not parsed.netloc):
            parts.append('<a target="_blank" rel="noopener" href="'+escape(href, quote=True)+'">'+escape(label)+'</a>')
        else:
            parts.append(escape(label))
        offset = match.end()
    parts.append(escape(text[offset:]))
    return re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', ''.join(parts))


def render_report(text):
    lines, result, i = text.splitlines(), [], 0
    heading_number = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[:\- ]+', c or '-') for c in cells):
                    rows.append((i, cells))
                i += 1
            result.append('<div class="report-table"><table>')
            for n, (source_line, cells) in enumerate(rows):
                tag = 'th' if n == 0 else 'td'
                result.append('<tr>'+''.join(f'<{tag} data-md-line="{source_line}" data-md-cell="{k}">'+inline(c)+f'</{tag}>' for k,c in enumerate(cells))+'</tr>')
            result.append('</table></div>')
            continue
        heading = re.match(r'^(#{1,6})\s+(.+)', line)
        if heading:
            level = min(len(heading[1]) + 1, 6)
            heading_number += 1
            result.append(f'<h{level} id="report-heading-{heading_number}" data-md-line="{i}">'+inline(heading[2])+f'</h{level}>')
        elif line.startswith('- '):
            result.append(f'<p class="report-bullet" data-md-line="{i}">'+inline(line[2:])+'</p>')
        else:
            result.append(f'<p data-md-line="{i}">'+inline(line)+'</p>')
        i += 1
    return '<article class="report-body">'+''.join(result)+'</article>'


def text_changes(before, after, bi):
    result = []
    old, new = before.splitlines(), after.splitlines()
    for kind, a, b, c, d in SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if kind == 'equal':
            continue
        if kind in {'delete', 'replace'}:
            result.append('<div class="change-before"><strong>'+bi('删除 / 修改前', 'Removed / before')+'</strong><pre>'+escape('\n'.join(old[a:b]))+'</pre></div>')
        if kind in {'insert', 'replace'}:
            result.append('<div class="change-after"><strong>'+bi('新增 / 修改后', 'Added / after')+'</strong><pre>'+escape('\n'.join(new[c:d]))+'</pre></div>')
    return ''.join(result)


def answer_text(answer):
    if isinstance(answer, str):
        return answer
    if not isinstance(answer, dict):
        return ''
    if 'report_markdown' in answer:
        return answer['report_markdown']
    lines = [c.get('text', '') for c in answer.get('claims', []) if isinstance(c, dict)]
    lines += answer.get('limitations', []) + answer.get('findings', [])
    return '\n\n'.join(lines)


def answer_changes(before, after, bi):
    """Present persisted revision values with locations in each version."""
    def blocks(answer):
        if not isinstance(answer, dict):
            return [('正文', 'Body', str(answer or ''))]
        if 'report_markdown' in answer:
            # Line locations are exact source positions, including table rows.
            return [(f'正文第 {i} 行', f'Body line {i}', line)
                    for i, line in enumerate(answer['report_markdown'].splitlines(), 1) if line.strip()]
        rows = [(f'第 {i} 段判断', f'Claim paragraph {i}', c.get('text', ''))
                for i, c in enumerate(answer.get('claims', []), 1)]
        for field, zh, en in [('limitations','未知项','Limitation'),('findings','核查发现','Finding')]:
            rows.extend((f'{zh} {i}', f'{en} {i}', text) for i,text in enumerate(answer.get(field, []),1))
        return rows
    old, new = blocks(before), blocks(after)
    result = []
    for kind,a,b,c,d in SequenceMatcher(None,[x[2] for x in old],[x[2] for x in new],autojunk=False).get_opcodes():
        if kind == 'equal':
            continue
        for offset in range(max(b-a,d-c)):
            left = old[a+offset] if a+offset < b else None
            right = new[c+offset] if c+offset < d else None
            result.append('<article class="paragraph-change">')
            for item, css, zh, en in [(left,'change-before','修改前','Before'),(right,'change-after','修改后','After')]:
                label = bi(item[0],item[1]) if item else bi('无（新增或删除）','None (addition or deletion)')
                result.append('<div class="'+css+'"><strong>'+bi(zh,en)+' · '+label+'</strong><pre>'+escape(str(item[2]) if item else '—')+'</pre></div>')
            result.append('</article>')
    return ''.join(result)


def report_outline(answer, bi):
    if not isinstance(answer, dict) or not answer.get('report_markdown'):
        return ''
    headings = re.findall(r'^#{1,6}\s+(.+)', answer['report_markdown'], re.M)
    if not headings: return ''
    return '<nav class="report-outline" aria-label="Report outline"><h2>' + bi('报告目录', 'Report outline') + '</h2>' + ''.join('<a href="#report-heading-'+str(i)+'">'+escape(title)+'</a>' for i,title in enumerate(headings,1)) + '</nav>'
