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
                    rows.append(cells)
                i += 1
            result.append('<div class="report-table"><table>')
            for n, cells in enumerate(rows):
                tag = 'th' if n == 0 else 'td'
                result.append('<tr>'+''.join(f'<{tag}>'+inline(c)+f'</{tag}>' for c in cells)+'</tr>')
            result.append('</table></div>')
            continue
        heading = re.match(r'^(#{1,6})\s+(.+)', line)
        if heading:
            level = min(len(heading[1]) + 1, 6)
            heading_number += 1
            result.append(f'<h{level} id="report-heading-{heading_number}">'+inline(heading[2])+f'</h{level}>')
        elif line.startswith('- '):
            result.append('<p class="report-bullet">• '+inline(line[2:])+'</p>')
        else:
            result.append('<p>'+inline(line)+'</p>')
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


def report_outline(answer, bi):
    if not isinstance(answer, dict) or not answer.get('report_markdown'):
        return ''
    headings = re.findall(r'^#{1,6}\s+(.+)', answer['report_markdown'], re.M)
    if not headings: return ''
    return '<nav class="report-outline" aria-label="Report outline"><h2>' + bi('报告目录', 'Report outline') + '</h2>' + ''.join('<a href="#report-heading-'+str(i)+'">'+escape(title)+'</a>' for i,title in enumerate(headings,1)) + '</nav>'
