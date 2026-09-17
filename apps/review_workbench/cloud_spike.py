"""Read-only inspector for independently generated Cloud runs."""
import gzip
import hashlib
import html as escaping
import json
import re
from pathlib import Path

from lxml import html
from apps.review_workbench.visual_system import workbench_page


def source_fragment(e, tree):
    path = re.sub(r"([\w-]+:[\w-]+)", r"*[name()='\1']", e["dom_path"])
    element = tree.xpath(path)[0]
    fragment = html.fromstring(html.tostring(element, encoding="unicode"))
    for script in fragment.xpath(".//script|.//iframe"):
        script.drop_tree()
    for descendant in fragment.iter():
        for attr in list(descendant.attrib):
            if attr.lower().startswith("on"):
                del descendant.attrib[attr]
    if e["cell"]:
        table = fragment if fragment.tag == "table" else fragment.xpath(".//table")[0]
        row = table.xpath("./tr|./tbody/tr|./thead/tr|./tfoot/tr")[e["cell"]["row"]]
        column = 0
        for cell in row.xpath("./td|./th"):
            if column == e["cell"]["column"]:
                cell.set("style", cell.get("style", "") + ";background:#fff0a8;outline:3px solid #ae7c00")
            column += int(cell.get("colspan", "1"))
    return html.tostring(fragment, encoding="unicode")


def approved_review(run_dir: Path):
    """Human decisions apply only to the exact reviewed snapshot, never a rerun."""
    folder = run_dir.parents[3] / "experiments/google_cloud_spike" / run_dir.name / "reviews"
    sha = hashlib.sha256((run_dir / "snapshot.json").read_bytes()).hexdigest()
    decisions = [json.loads(p.read_text()) for p in folder.glob("*.json")]
    matching = [r for r in decisions if r.get("run_id") == run_dir.name and r.get("snapshot_sha256") == sha]
    latest = max(matching, key=lambda r: r["recorded_at"], default=None)
    return latest if latest and latest.get("decision") == "approved" else None


@workbench_page('cloud')
def render_cloud_spike(run_dir: Path, source_dir: Path) -> str:
    snapshot = json.loads((run_dir / "snapshot.json").read_text())
    run = json.loads((run_dir / "run.json").read_text())
    trace = json.loads((run_dir / "trace.json").read_text())
    raw = gzip.decompress((source_dir / "source.html.gz").read_bytes())
    tree = html.document_fromstring(raw, parser=html.HTMLParser(encoding="utf-8"))
    esc = escaping.escape
    labels = {"offerings": ("Offerings", "产品组成"), "revenue": ("Revenue", "收入"),
              "operating_income": ("Operating income", "营业利润")}

    def bi(en, zh):
        return f"<span lang='en'>{esc(en)}</span><span lang='zh'>{esc(zh)}</span>"

    review = approved_review(run_dir)
    status = bi('Independent extraction · reviewed', '独立提取 · 审核通过') if review else bi('Independent extraction · candidate', '独立提取 · 待审核')
    review_html = ""
    if review:
        review_html = f"<p>{bi('Seven facts and evidence approved by you','7 条数据及出处已由你审核通过')} · {esc(review['recorded_at'][:10])}</p><details><summary>{bi('Human review record','人工审核记录')}</summary><pre>{esc(json.dumps(review,ensure_ascii=False,indent=2))}</pre></details>"
    analysis_links = []
    for path in (run_dir.parents[3] / "experiments/cloud_analysis").glob("analysis-*/run.json"):
        metadata = json.loads(path.read_text())
        if metadata.get("status") == "candidate" and metadata.get("input_run_id") == run_dir.name:
            stage = 'A1' if metadata.get('fixture') else 'A0'
            analysis_links.append(f"<p><a href='/analysis?run={esc(path.parent.name)}'>{bi('Open Analysis ' + stage,'查看 Analysis ' + stage)}</a></p>")
    note = (bi('This snapshot is approved. Historical comparison retains its original review status; approval does not transfer to other runs.',
               '本快照审核通过。历史评测保留当时的待审核状态；本次批准不自动应用于其他运行。') if review else
            bi('Reference review pending.', 'Reference 待人工审核。'))
    is_llm = run["method"] == "llm_extraction"
    method = bi("LLM extraction", "LLM 提取") if is_llm else bi("Rule extraction", "规则提取")
    links = []
    for path in sorted(run_dir.parent.glob("run-*/run.json")):
        other = json.loads(path.read_text())
        if other.get("status") != "candidate" or not (path.parent / "snapshot.json").exists():
            continue
        label = other.get("model") or "Rules"
        selected = " aria-current='page'" if path.parent == run_dir else ""
        links.append(f"<a{selected} href='/result?view=cloud-spike&amp;run={esc(path.parent.name)}'>{esc(label)} · {esc(other['started_at'][:19])}</a>")
    evaluation_path = run_dir.parents[3] / "experiments/google_cloud_spike" / run_dir.name / "evaluation.json"
    evaluation = json.loads(evaluation_path.read_text()) if evaluation_path.exists() else None
    evaluation_html = bi("Not evaluated", "尚未评测")
    if evaluation:
        evaluation_html = bi(f"{evaluation['actual_records']} records / {len(evaluation['errors'])} differences from candidate reference",
                             f"{evaluation['actual_records']} 条结果 / 与候选参考差异 {len(evaluation['errors'])} 项")
        evaluation_html += f"<details><summary>{bi('Comparison details','对照明细')}</summary><pre>{esc(json.dumps(evaluation,ensure_ascii=False,indent=2))}</pre></details>"
    request_path = run_dir / "request.json"
    request_html = ""
    if request_path.exists():
        request_html = f"<details><summary>{bi('Actual model input (source only)','实际模型输入（仅原文）')}</summary><pre>{esc(request_path.read_text())}</pre></details>"
    buttons, sections = [], []
    for i, fact in enumerate(snapshot["facts"]):
        e = snapshot["evidence"][fact["evidence_ids"][0]]
        fragment = source_fragment(e, tree)
        value = " · ".join(fact["value"]) if isinstance(fact["value"], list) else f"{fact['value']:,}"
        label = bi(*labels[fact["predicate"]])
        period = fact["period"] or ""
        buttons.append(f"<button class='fact' data-target='e{i}'>{label} <small>{period}</small><strong>{esc(value)}</strong></button>")
        sections.append(f"<section id='e{i}' class='evidence' hidden><h2>{label} {period}</h2>"
                        f"<p>{bi('Original-layout excerpt · reported page', '原版式片段 · 报告页码')} {e['reported_page']}</p>"
                        f"<div class='source'>{fragment}</div>"
                        f"<details><summary>{bi('Source location', '来源定位')}</summary><pre>{esc(json.dumps(e, ensure_ascii=False, indent=2))}</pre></details></section>")
    return f"""<!doctype html><html lang='zh'><meta charset='utf-8'><title>Google Cloud · Data Agent Spike</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;color:#24352c;font:14px/1.6 system-ui;background:#fafbf9}}[lang=en]{{display:none}}body.en [lang=zh]{{display:none}}body.en [lang=en]{{display:inline}}header{{padding:16px 24px;border-bottom:1px solid #dbe2dc;display:flex;gap:20px;align-items:center;background:white}}header a{{margin-left:auto;color:#256549}}button{{cursor:pointer;font:inherit}}header button{{border:0;background:none}}main{{display:grid;grid-template-columns:minmax(330px,36%) 1fr;height:calc(100vh - 66px)}}aside,article{{overflow:auto;padding:22px}}aside{{border-right:1px solid #dbe2dc}}h1{{font-size:21px;margin:0}}h2{{font-size:18px}}p,small{{color:#68776d}}.fact{{display:block;width:100%;text-align:left;padding:14px 8px;border:0;border-bottom:1px solid #dbe2dc;background:transparent}}.fact strong{{display:block;font-size:17px}}.fact.active{{background:#e7f1e9;border-left:3px solid #286348}}.source{{background:white;padding:20px;overflow:auto}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:11px}}details{{margin-top:20px}}.identity{{font:11px monospace;overflow-wrap:anywhere}}@media(max-width:760px){{main{{grid-template-columns:1fr;height:auto}}aside,article{{overflow:visible}}}}
</style><style>.runs a{{display:block;font-size:12px;color:#256549}}.runs a[aria-current]{{font-weight:bold}}.assessment{{padding:10px 0;border-bottom:1px solid #dbe2dc}}</style><body><header><b>Uteki / Data</b>{status}<a href='/result'>{bi('Business view','业务视图')}</a><button id='language'>EN / 中文</button></header>
<main><aside><h1>Google Cloud</h1><p>{bi('FY2025 filing · three comparative years · USD millions','FY2025 申报 · 三年比较数据 · 单位：百万美元')}</p>
<p>{method} · {esc(run.get('resolved_model') or run.get('model') or 'deterministic')}<br>{bi('Source filing date','材料提交日')} {esc(snapshot['available_at'])}</p>
<details class='runs'><summary>{bi('Select extraction run','切换提取版本')}</summary>{''.join(links)}</details>
<div class='assessment'>{evaluation_html}{review_html}{''.join(analysis_links)}</div>
{''.join(buttons)}{request_html}<details><summary>{bi(f'Read simulation: {len(trace)} tool calls',f'读取模拟：{len(trace)} 次工具调用')}</summary><pre>{esc(json.dumps(trace, ensure_ascii=False, indent=2))}</pre></details>
<details><summary>{bi('Run and coverage','运行与覆盖范围')}</summary><pre>{esc(json.dumps(run, ensure_ascii=False, indent=2))}</pre></details>
<p class='identity'>{esc(run_dir.name)}<br>{esc(snapshot['snapshot_id'])}</p>
<p>{note} {bi('Quarterly data is not extracted. This is not an autonomous analysis run.','季度数据尚未提取。本次为固定读取模拟，不代表自主分析已完成。')}</p></aside>
<article>{''.join(sections)}</article></main>
<script>const buttons=[...document.querySelectorAll('.fact')];function select(button){{buttons.forEach(b=>b.classList.toggle('active',b===button));document.querySelectorAll('.evidence').forEach(e=>e.hidden=e.id!==button.dataset.target)}}buttons.forEach(b=>b.onclick=()=>select(b));select(buttons[0]);document.getElementById('language').onclick=()=>document.body.classList.toggle('en');</script></body></html>"""
