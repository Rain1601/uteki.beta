"""Render an actual annual-only agent result without rewriting its conclusions."""
import argparse
import json
from html import escape
from pathlib import Path
from urllib.parse import quote


def render(folder, review=None):
    manifest = json.loads((folder / 'manifest.json').read_text())
    result = json.loads((folder / 'run/result.json').read_text())
    costs = json.loads((folder / 'run/costs.json').read_text())
    report = result['report']
    docs = {d['id']: d for d in manifest['documents']}

    def paragraph(p):
        refs = []
        for c in p['citations']:
            d = docs.get(c['document_id'])
            if not d:
                refs.append('<span>引用未匹配 / Unmatched source</span>')
                continue
            url = (f'/companies/{d["company_id"]}/documents/{d["accession"]}/indexes/'
                   f'{Path(d["index_folder"]).name}/source#{quote(c["block_id"], safe="")}')
            full = c.get('quote')
            if not full:
                refs.append(f'<a href="{escape(url)}" target="_blank" rel="noopener">引用待核实：未实际读取 <small>[2025 10-K]</small></a>')
                continue
            label = full[:42] + ('…' if len(full) > 42 else '')
            refs.append(f'<a href="{escape(url)}" target="_blank" rel="noopener" title="{escape(full, quote=True)}">{escape(label)} <small>[2025 10-K]</small></a>')
        source = '； '.join(refs[:3])
        if len(refs) > 3:
            source += '<details><summary>展开更多 / More</summary>' + '； '.join(refs[3:]) + '</details>'
        return f'<p>{escape(p["text"])}</p>' + (f'<div class="sources">依据 / Sources：{source}</div>' if refs else '')

    nav = '<a href="#thesis">核心判断<small>Thesis</small></a>'
    content = f'<section id="thesis"><h2>核心判断 <small>Thesis</small></h2>{paragraph(report["thesis"])}</section>'
    seen = {}
    for s in report['sections']:
        key = escape(s['key'], quote=True)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            key += '-' + str(seen[key])
        label = {'business':'公司做什么','industry':'行业与竞争','earnings':'赚钱与增长','valuation':'价格是否合适','watch':'接下来关注什么'}[s['key']]
        nav += f'<a href="#{key}">{label}<small>{key.title()}</small></a>'
        content += f'<section id="{key}"><h2>{escape(s["title"])}</h2>' + ''.join(paragraph(p) for p in s['paragraphs']) + '</section>'
    errors = result['validation_errors']
    status = '自动检查未通过 / Validation failed' if errors else '引用定位与结构校验通过 · 尚待人工审核 / Pending review'
    if review and review.get('errors'):
        status += '；百分比复核未通过 / Percentage coverage unresolved: ' + escape('; '.join(review['errors']))
    limitations = ''.join(f'<li>{escape(x)}</li>' for x in report['limitations'])
    logs = []
    for path in sorted((folder / 'run').glob('tool-*.json')):
        entry = json.loads(path.read_text())
        logs.append(f'<li>{escape(entry["tool"])}：{escape(entry.get("reason", ""))} <a href="run/{path.name}">记录 / Record</a></li>')
    rows = ''.join(f'<tr><td>{i}</td><td>{escape(r["status"])}</td><td>{(r.get("usage") or {}).get("input_tokens", "—")}</td><td>{(r.get("usage") or {}).get("output_tokens", "—")}</td><td>{escape(str(r.get("estimated_usd") or "未知"))}</td></tr>' for i, r in enumerate(costs['records'], 1))
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Alphabet · Single Agent 年报研究</title>
<style>
:root{{color-scheme:light}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:#fff;color:#243347;font:17px/1.9 "Avenir Next","PingFang SC","Microsoft YaHei",sans-serif}}a{{color:#285db0;text-underline-offset:4px}}a:focus-visible,summary:focus-visible{{outline:3px solid #285db0;outline-offset:4px}}.layout{{max-width:1220px;margin:auto;display:grid;grid-template-columns:220px minmax(0,1fr);gap:64px;padding:40px 28px}}aside{{position:sticky;top:32px;align-self:start;max-height:90vh;overflow:auto}}aside a{{display:block;padding:10px 14px;text-decoration:none;border-radius:6px}}aside a:hover{{background:#f7f9fc}}small{{font-size:13px;color:#68768a}}aside small{{display:block}}header{{margin-bottom:52px}}h1{{font-size:32px;line-height:1.5;margin:18px 0}}h2{{font-size:25px;line-height:1.6;margin:0 0 24px}}section{{scroll-margin-top:28px;margin:0 0 64px}}p{{margin:0 0 24px;overflow-wrap:anywhere}}.sources{{color:#68768a;font-size:14px;line-height:1.8;margin:-8px 0 32px}}.sources a{{display:inline;overflow-wrap:anywhere}}.notice{{font-size:14px;color:#68768a}}details{{margin:20px 0}}summary{{cursor:pointer;color:#285db0}}table{{width:100%;border-collapse:collapse;font-size:13px}}td,th{{padding:8px;text-align:left;border-bottom:1px solid #e0e6ef}}.scroll{{overflow:auto}}li{{margin-bottom:12px}}footer{{color:#68768a;font-size:14px;padding-bottom:50px}}@media(max-width:800px){{.layout{{display:block;padding:20px}}aside{{position:static;max-height:none;margin-bottom:32px}}nav{{display:flex;overflow:auto;gap:8px}}nav a{{min-width:125px;font-size:14px}}h1{{font-size:27px}}}}@media(prefers-reduced-motion:reduce){{html{{scroll-behavior:auto}}}}
</style><div class="layout"><aside><p>这份报告 / Contents</p><nav>{nav}</nav><p class="notice">FY2025 10-K<br>材料截止 2026-02-05<br>Single Agent · gpt-5.4-mini</p><a href="/experiments/codex-hypothesis-2025-2026-v0.1/annual-report.html">查看之前的整理版</a></aside><main><header><a href="/companies/alphabet?tab=research">Alphabet / 研究档案</a><h1>{escape(report['title'])}</h1><p class="notice">模型独立生成原文 / Independent model output<br>{status}</p><p class="notice">仅提供年报材料与阅读框架，未输入旧版结论。页面不改写模型判断；引用校验不等于分析正确。</p></header>{content}<section><h2>研究边界 <small>Limitations</small></h2><ul>{limitations}</ul><p class="notice">{escape(report['stop_reason'])}</p></section><details><summary>运行、引用检查与费用 / Run & cost</summary><p>模型调用 {costs['requests']} 次；工具调用 {result['tool_calls']} 次。估算费用 ${escape(costs['known_estimated_usd'])}；费用未知调用 {costs['unknown_cost_requests']} 次。</p><p class="notice">按 2026-09-13 保存的未缓存单价估算，不是实际账单。工具调用目的是操作摘要，不是模型私有思维链。校验错误：{escape(json.dumps(errors, ensure_ascii=False))}</p><div class="scroll"><table><thead><tr><th>调用</th><th>状态</th><th>输入 tokens</th><th>输出 tokens</th><th>估算 USD</th></tr></thead><tbody>{rows}</tbody></table></div><ol>{''.join(logs)}</ol><p><a href="run/result.json">完整结果</a> · <a href="run/costs.json">费用记录</a> · <a href="manifest.json">冻结的运行配置</a></p></details><footer>实验候选 · 不自动采纳 · 不代表投资建议 / Research candidate</footer></main></div></html>'''


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    (args.folder / 'review.html').write_text(render(args.folder), encoding='utf-8')
