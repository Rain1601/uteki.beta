"""Product hierarchy: home, company workspace, reports and their versions."""
from html import escape
from pathlib import Path
from urllib.parse import quote
import json
from apps.review_workbench.visual_system import workbench_page
from apps.review_workbench.company_data import material_table


def e(value):
    return escape(str(value or ''), quote=True)


def bi(zh,en):
    return '<span lang="zh">'+e(zh)+'</span><span lang="en">'+e(en)+'</span>'


def company_tabs(company_id, active='overview'):
    base='/companies/'+quote(company_id,safe='')
    return '<nav class="company-tabs" aria-label="Company sections">'+''.join(
        '<a '+('aria-current="page" ' if key==active else '')+'href="'+base+suffix+'">'+bi(zh,en)+'</a>'
        for key,suffix,zh,en in [('overview','','研究详情','Research'),('reports','/reports','分析报告','Reports'),('materials','/materials','原始材料','Materials'),('data','/data','结构化数据','Structured data')])+'</nav>'


def crumb(company=None, section=None):
    result='<nav class="breadcrumbs" aria-label="Breadcrumb"><a href="/">'+bi('主页','Home')+'</a>'
    if company:
        result+='<span>/</span><a href="/companies">'+bi('公司','Companies')+'</a><span>/</span><a href="/companies/'+e(company['id'])+'">'+e(company['name'])+'</a>'
    if section: result+='<span>/</span><span>'+bi(*section)+'</span>'
    return result+'</nav>'


@workbench_page('workspace')
def page(title, body):
    return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+e(title)+' · Uteki</title><style>'+CSS+'</style></head><body><div class="workspace-language"><button id="workspace-language">中文 / EN</button></div><main class="workspace-main">'+body+'</main><script>document.documentElement.dataset.language=localStorage.getItem("data-language")||"zh";document.getElementById("workspace-language").onclick=()=>{const l=document.documentElement.dataset.language==="en"?"zh":"en";document.documentElement.dataset.language=l;localStorage.setItem("data-language",l)};document.querySelectorAll("[data-list-filter]").forEach(input=>input.addEventListener("input",()=>{const q=input.value.trim().toLowerCase();const rows=[...document.querySelectorAll(input.dataset.listFilter)];rows.forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));const empty=document.getElementById("filter-empty");if(empty)empty.hidden=rows.some(r=>!r.hidden)}));function filterMaterials(){const q=(document.querySelector(\'#search\')?.value||\'\').toLowerCase(),y=document.querySelector(\'#year\')?.value||\'\',f=document.querySelector(\'#form\')?.value||\'\';document.querySelectorAll(\'tr[data-search]\').forEach(r=>r.hidden=!(r.dataset.search.includes(q)&&(!y||r.dataset.year===y)&&(!f||r.dataset.form===f)))}document.querySelectorAll(\'.controls input,.controls select\').forEach(x=>x.addEventListener(\'input\',filterMaterials));</script></body></html>'


def report_groups(rows):
    by_id={r['id']:r for r in rows}
    groups={}
    for row in rows:
        root=row;seen=set()
        while root.get('parent_snapshot_id') in by_id and root['id'] not in seen:
            seen.add(root['id']);root=by_id[root['parent_snapshot_id']]
        groups.setdefault(root['id'],[]).append(row)
    result=[]
    for family in groups.values():
        visible=[r for r in family if r.get('status')!='deleted']
        if not visible: continue
        latest=max(visible,key=lambda r:r.get('created_at') or r.get('run_started_at') or '')
        effective=next((r for r in visible if r.get('status')=='adopted'),None)
        result.append((effective or latest,latest,family))
    return sorted(result,key=lambda item:item[1].get('created_at') or item[1].get('run_started_at') or '',reverse=True)


def report_list(rows, limit=None):
    groups=report_groups(rows)
    if limit is not None: groups=groups[:limit]
    if not groups: return '<p class="workspace-empty">'+bi('还没有研究报告。先进入公司材料库，确认研究范围。','No research reports yet. Start with the company materials.')+'</p>'
    result='<div class="report-directory">'
    statuses={'candidate':('待审核','Pending review'),'adopted':('已采纳','Adopted'),'archived':('已归档','Archived'),'rejected':('已拒绝','Rejected')}
    for row, latest, family in groups:
        label=row.get('title') or row.get('question') or '研究报告'
        result+='<article class="report-list-row"><div><a class="report-title" href="/companies/'+quote(row['company_id'],safe='')+'/reports/'+quote(row['id'],safe='')+'">'+e(label)+'</a><p>'+e(row.get('primary_title') or row.get('primary_document_id'))+'</p><small>'+e(row.get('researcher_label') or row.get('researcher_id'))+' · '+e((row.get('created_at') or row.get('run_started_at') or '')[:10])+'</small></div><div class="report-list-state"><span class="report-status">'+bi(*statuses.get(row.get('status'),('待确认','Unconfirmed')))+'</span><small>'+bi(f'{len(family)} 个版本',f'{len(family)} versions')+'</small>'
        if latest['id']!=row['id']:
            result+='<a href="/companies/'+quote(latest['company_id'],safe='')+'/reports/'+quote(latest['id'],safe='')+'">'+bi('查看最新修订','Latest revision')+'</a>'
        result+='</div></article>'
    return result+'</div>'


def render_reports(rows, company=None):
    heading=bi('研究报告','Research reports')
    body=crumb(company,('研究报告','Reports'))+(company_tabs(company['id'],'reports') if company else '')
    body+='<div class="workspace-heading"><h1>'+heading+'</h1><p>'+bi('每份报告的人工和 Agent 修订保留在同一条版本历史中。','Human and agent revisions stay in the same report history.')+'</p></div><label class="directory-search">'+bi('查找报告','Find a report')+'<input type="search" data-list-filter=".report-list-row" placeholder="公司 / 标题 / 研究者"></label>'+report_list(rows)+'<p id="filter-empty" hidden>'+bi('没有匹配的报告。','No matching reports.')+'</p>'
    return page('研究报告',body)


def render_company_overview(company, rows, catalog, bundle=None):
    from apps.review_workbench.company_brief import render_brief
    return render_brief(company, rows, catalog, bundle)


def render_materials(company,catalog,reading):
    docs=catalog if company['id']=='alphabet' else {'documents':[]}
    body=crumb(company,('材料库','Materials'))+company_tabs(company['id'],'materials')+'<div class="workspace-heading"><h1>'+bi('材料库','Source materials')+'</h1><p>'+bi('原文、文档目录和页码定位在这里；研究结论请进入报告。','Find sources, document outlines and locators here. Research conclusions live in reports.')+'</p></div>'
    body+='<h2>'+bi('可检索材料与文档目录','Searchable materials & outlines')+'</h2>'+material_table(docs)
    body+='<h2>'+bi('PDF 阅读资料','PDF reading library')+'</h2><p class="muted">'+bi('PDF 与上面的索引可能对应同一材料，不相加计算覆盖量。下载不代表已全文翻译或通过研究审核。','PDFs may duplicate indexed documents. Downloads do not imply translation or research approval.')+'</p>'
    if reading:
        body+='<div class="workspace-table"><table><thead><tr><th>'+bi('报告期','Period')+'</th><th>'+bi('材料','Material')+'</th><th>'+bi('原文','Original')+'</th></tr></thead><tbody>'
        kinds={'release':'业绩发布稿','slides':'业绩演示','transcript':'电话会文字稿','annual-report':'年度报告'}
        for doc in sorted(reading,key=lambda d:d['period'],reverse=True):
            stem=Path(doc['path']).stem
            body+='<tr><td>'+e(doc['period'])+'</td><td>'+e(kinds.get(doc['kind'],doc['kind']))+'</td><td><a href="/companies/alphabet/materials/pdf/'+quote(stem,safe='')+'">'+bi('打开 PDF','Open PDF')+'</a></td></tr>'
        body+='</tbody></table></div>'
    else: body+='<p>'+bi('尚未采集 PDF。','No PDFs collected yet.')+'</p>'
    return page('材料库',body)


def render_structured(company,bundle):
    body=crumb(company,('结构化数据','Structured data'))+company_tabs(company['id'],'data')+'<div class="workspace-heading"><h1>'+bi('结构化数据','Structured research data')+'</h1><p>'+bi('财务指标与业务结构，每项数据保留出处。','Financial metrics and business structure, with evidence retained.')+'</p></div>'
    if not bundle:
        return page('结构化数据',body+'<p>'+bi('此公司尚未生成结构化研究数据。','No structured research data for this company yet.')+'</p>')
    body+='<p class="coverage-note">'+bi('当前覆盖 FY2025；候选数据待审核。季度原文已采集，不代表季度指标已整理完成。','FY2025 coverage; candidate data awaits review. Collected quarterly sources do not imply extracted quarterly metrics.')+'</p><div class="section-heading"><h2>'+bi('业务结构','Business structure')+'</h2><a href="/companies/alphabet/data/business-map">'+bi('查看业务图与证据','Business map & evidence')+'</a></div><h2>'+bi('财务指标','Financial metrics')+'</h2><div class="workspace-table"><table><thead><tr>'+''.join('<th>'+bi(*x)+'</th>' for x in [('业务','Business'),('指标','Metric'),('期间','Period'),('数值（百万美元）','Value (USD millions)'),('出处','Evidence')])+'</tr></thead><tbody>'
    for metric in bundle['metrics']:
        name={'revenue':'收入','operating_income':'营业利润','operating_loss':'营业亏损'}.get(metric['metric'],metric['metric'])
        body+='<tr><td>'+e(metric['business_id'])+'</td><td>'+bi(name,metric['metric'])+'</td><td>'+e(metric['period'])+'</td><td>'+e(format(metric['value'],','))+'</td><td><a href="/companies/alphabet/data/business-map?selected='+quote(metric['business_id'],safe='')+'">'+bi('查看出处','View source')+'</a></td></tr>'
    body+='</tbody></table></div><h2>'+bi('已知数据缺口','Known gaps')+'</h2><p>'+bi('跨期指标、现金流、资本开支和估值输入尚未进入这个数据包。','Cross-period metrics, cash flow, capital expenditure and valuation inputs are not in this bundle.')+'</p>'
    return page('结构化数据',body)


CSS='''
*{box-sizing:border-box}body{margin:0;font:15px/1.7 "Avenir Next","PingFang SC",sans-serif;color:var(--ink);background:#fff}a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}button,input{font:inherit}button{background:white;border:1px solid var(--line2);padding:6px 12px;border-radius:5px;cursor:pointer}[lang=en]{display:none}html[data-language=en] [lang=en]{display:inline}html[data-language=en] [lang=zh]{display:none}[hidden]{display:none!important}.workspace-main{max-width:1250px;margin:auto;padding:24px 36px 80px}.workspace-language{display:flex;justify-content:flex-end;padding:8px 36px}.breadcrumbs{display:flex;gap:10px;flex-wrap:wrap;font-size:13px;color:var(--muted)}.workspace-heading{margin:30px 0}.workspace-heading h1{font-size:28px;margin:0 0 8px}.workspace-heading p,.muted{color:var(--muted)}.home-layout{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:60px}.continue-report{padding:22px 28px;background:var(--rail);border-left:4px solid var(--accent)}.continue-report h3{font-size:20px;line-height:1.6;margin:10px 0}.primary-link{display:inline-block;padding:9px 17px;background:var(--accent);color:#fff;border-radius:5px;margin-top:8px}.home-context{padding-top:0}.home-context h2{margin:0 0 18px}.company-shortcut{display:flex;justify-content:space-between;border-bottom:1px solid var(--line2);padding:12px 0}.research-path{padding-left:20px;font-size:14px}.research-path li{padding:9px 0}.home-context>h2:not(:first-child){margin-top:36px}.section-heading{display:flex;align-items:center;justify-content:space-between;margin-top:34px}.report-list-row{display:flex;justify-content:space-between;gap:24px;border-bottom:1px solid var(--line2);padding:20px 0}.report-title{font-size:17px;font-weight:600}.report-list-row p{margin:5px 0;color:var(--muted)}.report-list-row small{font-size:12px;color:var(--muted);display:block}.report-list-state{flex:0 0 115px;text-align:right}.report-status{font-size:13px;color:var(--muted)}.company-tabs{display:flex;gap:28px;border-bottom:1px solid var(--line2);margin:22px 0;overflow:auto}.company-tabs a{padding:12px 0;white-space:nowrap}.company-tabs a[aria-current]{border-bottom:2px solid var(--accent);font-weight:600}.company-sections{display:grid;grid-template-columns:repeat(3,1fr);gap:35px;margin:32px 0}.company-section{color:var(--ink);border-bottom:2px solid var(--line2);padding-bottom:20px}.company-section h2{font-size:20px}.company-section p{color:var(--muted);font-size:14px}.workspace-table,.scroll{overflow:auto}.workspace-table table,.scroll table{border-collapse:collapse;width:100%;font-size:13px}.workspace-table th,.workspace-table td,.scroll td,.scroll th{text-align:left;padding:12px;border-bottom:1px solid var(--line2);vertical-align:top}.workspace-table th,.scroll th{background:var(--rail)}.directory-search{display:flex;gap:16px;align-items:center}.directory-search input{padding:8px 12px;border:1px solid var(--line2);border-radius:5px;min-width:260px}.coverage-note{border-left:3px solid var(--accent);background:var(--rail);padding:15px 20px}.controls{display:flex;gap:12px;margin:20px 0}.controls input,.controls select{padding:8px;border:1px solid var(--line2);border-radius:4px}.workspace-main h2{margin-top:28px}.workspace-main small{display:block}.workspace-empty{padding:25px 0;color:var(--muted)}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid var(--accent);outline-offset:3px}@media(max-width:800px){.home-layout{grid-template-columns:1fr;gap:30px}.home-context{border-top:1px solid var(--line2);padding-top:25px}.workspace-main{padding:20px}.company-sections{grid-template-columns:1fr;gap:12px}.company-tabs{gap:20px}.controls{flex-wrap:wrap}.directory-search{display:block}.directory-search input{display:block;width:100%;min-width:0}.report-list-row{gap:12px}.report-list-state{flex-basis:84px}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
'''

CSS += """
.company-research-layout{display:grid;grid-template-columns:minmax(0,1fr) 270px;gap:48px}.company-report-main>.section-heading{margin-top:0}.company-report-main>.section-heading h2{margin-top:0}.featured-report{padding:20px 25px;background:var(--rail);border-left:3px solid var(--accent);margin:12px 0 32px}.featured-report h3{font-size:23px;line-height:1.5;margin:8px 0 14px;font-weight:600}.featured-report>p{font-size:14px;max-width:60ch}.research-support{border-left:1px solid var(--line2);padding-left:28px}.research-support h2{margin-top:0}.support-link{display:block;margin:24px 0 6px}.support-link strong,.support-link span{display:block}.support-link span,.research-support>.muted,.index-guidance p{font-size:13px;color:var(--muted);margin-top:5px}.index-guidance{margin-top:26px;font-size:13px}.index-guidance summary{cursor:pointer;color:var(--muted)}@media(max-width:850px){.company-research-layout{grid-template-columns:1fr;gap:30px}.research-support{border-left:0;border-top:1px solid var(--line2);padding:24px 0 0}.featured-report{padding:18px}.featured-report h3{font-size:20px}}
"""
