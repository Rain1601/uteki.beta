"""Read-only, evidence-linked view of the minimal Analysis Agent run."""
import html as escaping
import gzip
import json
from pathlib import Path

from lxml import html
from apps.review_workbench.visual_system import workbench_page

from apps.review_workbench.cloud_spike import source_fragment
from uteki.infrastructure.research_data.cloud_spike import digest


def analysis_approval(folder):
    decisions = [json.loads(p.read_text()) for p in (folder / 'reviews').glob('*.json')]
    required = {'run.json', 'answer.json', 'input_snapshot.json', 'comparisons.json', 'trace.json', 'evaluation.json'}
    matching = [r for r in decisions if r.get('run_id') == folder.name and
                set(r.get('artifact_sha256', {})) == required and
                all((folder / n).is_file() and digest((folder / n).read_bytes()) == sha for n, sha in r['artifact_sha256'].items())]
    latest = max(matching, key=lambda r: r['recorded_at'], default=None)
    return latest if latest and latest.get('decision') == 'approved' else None


@workbench_page('cloud')
def render_cloud_analysis(folder: Path, root: Path):
    def read(name):
        return json.loads((folder / name).read_text())
    run, answer, snapshot = read("run.json"), read("answer.json"), read("input_snapshot.json")
    gap = bool(run.get('fixture'))
    if gap:
        snapshot = read('resolved_snapshot.json')
    comparisons, trace, rounds = read("comparisons.json"), read("trace.json"), read("rounds.json")
    evaluation = read("evaluation.json") if (folder / "evaluation.json").exists() else None
    esc = escaping.escape
    def bi(en, zh):
        return f"<span lang='en'>{esc(en)}</span><span lang='zh'>{esc(zh)}</span>"
    facts = {f["fact_id"]: f for f in snapshot["facts"]}
    positions = {f["fact_id"]: i for i, f in enumerate(snapshot["facts"])}
    labels = {"revenue": ("Revenue", "收入"), "operating_income": ("Operating income", "营业利润")}
    raw = gzip.decompress((root / 'data/source_documents/alphabet_2025_10k/source.html.gz').read_bytes())
    tree = html.document_fromstring(raw, parser=html.HTMLParser(encoding='utf-8'))
    sections = []
    for fid, f in facts.items():
        if f['predicate'] not in labels:
            continue
        e = snapshot['evidence'][f['evidence_ids'][0]]
        recovered_note = bi('New source extraction · pending review','原文重新提取 · 待审核') if f.get('retrieval_origin') == 'source_recovery' else ''
        sections.append(f"<section class='evidence' id='e{positions[fid]}' hidden><h2>{bi(*labels[f['predicate']])} {esc(f['period'])}</h2><p>{bi('Reported page','报告页码')} {e['reported_page']} · {recovered_note}</p><div class='source'>{source_fragment(e,tree)}</div><details><summary>{bi('Source location','来源定位')}</summary><pre>{esc(json.dumps(e,ensure_ascii=False,indent=2))}</pre></details></section>")
    def fact_button(fid, label=None):
        f = facts[fid]
        return f"<button class='source-link' data-target='e{positions[fid]}'>{esc(label or format(f['value'], ','))}</button>"
    tables = []
    for metric in answer["metrics"]:
        annual = sorted(metric["annual_fact_ids"], key=lambda fid: facts[fid]["period"])
        values = ''.join(f"<td>{fact_button(fid)}</td>" for fid in annual)
        headers = ''.join(f"<th>{esc(facts[fid]['period'])}</th>" for fid in annual)
        rows = []
        for cid in metric["comparison_ids"]:
            c = comparisons[cid]
            a, b = facts[c["start_fact_id"]], facts[c["end_fact_id"]]
            target = "calc-" + cid
            rate = c['growth_percent'] + '%' if c['growth_percent'] is not None else '—'
            rows.append(f"<tr><td>{esc(a['period'])} → {esc(b['period'])}</td><td><button class='source-link' data-target='{target}'>{c['delta']:+,}</button></td><td><button class='source-link' data-target='{target}'>{esc(rate)}</button></td></tr>")
            sections.append(f"<section class='evidence' id='{target}' hidden><h2>{bi(*labels[metric['predicate']])} · {bi('Calculation','计算依据')}</h2><p>{a['period']} → {b['period']}</p><div class='formula'>({b['value']:,} − {a['value']:,}) ÷ {a['value']:,} × 100 = {esc(rate)}</div><p>{bi('Absolute change (USD millions)','变化额（百万美元）')}：{c['delta']:+,}</p><p>{bi('Open both inputs in the original filing','分别查看两项输入的原文')}</p>{fact_button(c['start_fact_id'], a['period'] + ' · ' + format(a['value'], ','))}　{fact_button(c['end_fact_id'], b['period'] + ' · ' + format(b['value'], ','))}<p>{bi('Derived calculation, not a directly disclosed statement. Rounded to two decimal places.','派生计算，不是原文直接披露的结论。百分比四舍五入至两位小数。')}</p></section>")
        tables.append(f"<h2>{bi(*labels[metric['predicate']])}</h2><table><thead><tr>{headers}</tr></thead><tbody><tr>{values}</tr></tbody></table><table><thead><tr><th>{bi('Interval','期间')}</th><th>{bi('Change · USD millions','变化额 · 百万美元')}</th><th>{bi('Growth','增长率')}</th></tr></thead><tbody>{''.join(rows)}</tbody></table>")
    tool_labels = {'manifest': ('Read coverage', '读取覆盖范围'), 'facts': ('Retrieve facts', '读取数据'),
                   'evidence': ('Read evidence', '读取出处'), 'compare': ('Calculate change', '计算变化'),
                   'request_missing': ('Record gap', '记录缺失'), 'source_lookup': ('Recover from source', '从原文补取')}
    trace_rows = ''.join(f"<details><summary>{t['step']:02d} · {bi(*tool_labels.get(t['tool'], (t['tool'],t['tool'])))}</summary><pre>{esc(json.dumps(t,ensure_ascii=False,indent=2))}</pre></details>" for t in trace)
    status = bi('Not evaluated','尚未评测') if evaluation is None else bi(f"{len(evaluation['errors'])} check errors · narrative review pending", f"核验错误 {len(evaluation['errors'])} 项 · 文字结论待审核")
    review = analysis_approval(folder)
    stage = 'A1' if gap else 'A0'
    badge = bi(stage + ' · approved', stage + ' · 审核通过') if review else bi(stage + ' · pending review', stage + ' · 待审核')
    review_html = ''
    if review:
        status = bi('This analysis was approved by you; historical checks remain unchanged.','本次分析已由你审核通过；历史评测记录保持不变。')
        review_html = f"<details><summary>{bi('Human review record','人工审核记录')}</summary><pre>{esc(json.dumps(review,ensure_ascii=False,indent=2))}</pre></details>"
    gap_html = ''
    if gap:
        gap_html = f"<p class='summary'>{bi('Controlled gap: FY2025 revenue withheld → Data-side source recovery. Recovered fact and analysis are pending review; the approved baseline is untouched.','受控缺失：隐藏 FY2025 收入 → Data 端原文补取。补取数据与分析均待审核；已审核基线保持不变。')}</p>"
        rejected = sum(t['response'].get('status') == 'tool_error' for t in trace)
        recovered = sum(t['tool'] == 'source_lookup' and t['response'].get('status') == 'recovered_candidate' for t in trace)
        gap_html += f"<p>{bi(f'Tool rejections: {rejected}; successful source recoveries: {recovered}. Full corrective sequence is in the trace.', f'工具调用被拒 {rejected} 次；原文补取成功 {recovered} 次。完整纠正过程见下方调用记录。')}</p>"
    limitation = (bi('Narrow rule-based source recovery, not general document search. No Thesis or causal explanation.','仅限窄范围规则补取，不是通用文档检索；不做 Thesis 或归因。') if gap else bi('No Thesis, causes, quarterly data or document retrieval. The live run had no missing data; missing-data behavior is unit-tested only.','本轮不做 Thesis、归因、季度数据或原文检索；本次运行未遇到缺失。'))
    return f"""<!doctype html><html lang='zh'><meta charset='utf-8'><title>Uteki · Google Cloud Analysis {stage}</title>
<style>*{{box-sizing:border-box}}body{{margin:0;font:14px/1.65 system-ui;color:#24352c;background:#fafbf9}}[lang=en]{{display:none}}body.en [lang=zh]{{display:none}}body.en [lang=en]{{display:inline}}header{{height:58px;padding:12px 24px;display:flex;align-items:center;gap:24px;border-bottom:1px solid #dbe2dc;background:white}}header a{{margin-left:auto}}a,button{{color:#256549}}button{{font:inherit;cursor:pointer}}header button{{border:0;background:none}}main{{display:grid;grid-template-columns:49% 51%;height:calc(100vh - 58px)}}aside,article{{padding:22px;overflow:auto}}aside{{border-right:1px solid #dbe2dc}}h1{{font-size:21px;margin:0 0 10px}}h2{{font-size:17px;margin-top:24px}}p,small{{color:#617466}}.summary{{border-left:3px solid #397556;padding-left:14px}}table{{width:100%;border-collapse:collapse;margin:10px 0}}td,th{{border-bottom:1px solid #dbe2dc;padding:8px;text-align:right}}td:first-child,th:first-child{{text-align:left}}th{{font-weight:500;font-size:12px;color:#617466}}.source-link{{border:0;background:transparent;text-decoration:underline;text-underline-offset:4px;padding:2px}}.source-link.active{{background:#e2efdf}}details{{margin:12px 0}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:11px}}.source{{background:white;padding:16px;overflow:auto}}.formula{{padding:16px;background:#e7f1e9;font-variant-numeric:tabular-nums}}.identity{{font-size:11px;overflow-wrap:anywhere}}@media(max-width:780px){{main{{grid-template-columns:1fr;height:auto}}aside,article{{overflow:visible}}}}</style>
<body><header><b>Uteki / Analysis</b>{badge}<a href='/result?view=cloud-spike&amp;run={esc(run['input_run_id'])}'>{bi('Approved data','已审核数据')}</a><button id='language'>EN / 中文</button></header>
<main><aside><h1>Google Cloud · {bi('Three-year changes','三年变化')}</h1><p>{bi('FY2025 filing presentation · USD millions','FY2025 申报口径 · 百万美元')}<br>{bi('Available as of','材料可用日')} {esc(run['as_of'])}</p>
{gap_html}<div class='summary'>{bi(answer['summary_en'],answer['summary_zh'])}</div><p>{status}</p>{review_html}
{''.join(tables)}<details><summary>{bi(f'Model-directed process · {run["model_calls"]} rounds / {run["tool_calls"]} tool calls', f'自主调用过程 · {run["model_calls"]} 轮 / {run["tool_calls"]} 次工具调用')}</summary>{trace_rows}</details>
<details><summary>{bi('Model actions by round','每轮模型动作')}</summary><pre>{esc(json.dumps(rounds,ensure_ascii=False,indent=2))}</pre></details>
<details><summary>{bi('Initial model input','模型首次输入')}</summary><pre>{esc(json.dumps(read('round-01-request.json'),ensure_ascii=False,indent=2))}</pre></details>
<details><summary>{bi('Run and checks','运行与核验')}</summary><pre>{esc(json.dumps({'run':run,'evaluation':evaluation},ensure_ascii=False,indent=2))}</pre></details>
<p>{limitation}</p><p class='identity'>{esc(folder.name)}</p></aside><article>{''.join(sections)}</article></main>
<script>const buttons=[...document.querySelectorAll('[data-target]')];function select(b){{document.querySelectorAll('.evidence').forEach(e=>e.hidden=e.id!==b.dataset.target);buttons.forEach(x=>x.classList.toggle('active',x.dataset.target===b.dataset.target));document.querySelector('article').scrollTop=0}}buttons.forEach(b=>b.onclick=()=>select(b));if(buttons.length)select(buttons[0]);document.getElementById('language').onclick=()=>document.body.classList.toggle('en');</script></body></html>"""
