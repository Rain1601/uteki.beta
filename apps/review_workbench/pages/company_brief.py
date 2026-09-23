"""Company overview led by recorded judgments, with source context alongside."""
from apps.review_workbench.assets import asset_text
from pathlib import Path
from urllib.parse import quote
from apps.review_workbench.components.site_navigation import bi, e, page, company_tabs, report_groups, report_list


def render_brief(company, rows, catalog, bundle=None):
    base='/companies/'+quote(company['id'],safe='')
    groups=report_groups(rows)
    docs=catalog.get('documents',[]) if company['id']=='alphabet' else []
    body='<div class="cb-heading"><div><a href="/companies" class="cb-back">'+bi('公司','Companies')+'</a><span class="cb-divider">/</span><h1>'+e(company['name'])+'</h1><span class="cb-ticker">'+e(company.get('ticker'))+'</span></div></div>'+company_tabs(company['id'])
    body+='<div class="cb-layout"><section class="cb-main"><header class="cb-section-head"><h2>'+bi('研究简报','Research brief')+'</h2><span>'+bi('来自已有报告','From recorded research')+'</span></header><div class="cb-scroll">'
    featured=groups[0][0] if groups else None
    if featured:
        answer=featured.get('answer') or {}
        claims=answer.get('claims',[]) if isinstance(answer,dict) else []
        statements=[c for c in claims if isinstance(c,dict) and c.get('text')]
        url=base+'/reports/'+quote(featured['id'],safe='')
        body+='<div class="featured-report"><p class="cb-eyebrow">'+bi('当前判断','Current view')+'</p>'
        if statements:
            body+='<p class="cb-lead">'+e(statements[0]['text'])+'</p>'
        else:
            text=(answer.get('report_markdown') or answer.get('text') or '') if isinstance(answer,dict) else str(answer)
            body+='<p class="cb-lead">'+(e(text[:1600]) if text else bi('这份报告尚未保存可展示的判断。','This report has no recorded judgment to preview.'))+'</p>'
            if len(text)>1600:body+='<p class="cb-meta">'+bi('正文节选；完整内容见报告。','Excerpt; see report for full text.')+'</p>'
        body+='</div>'
        # Preserve the original wording, order and fact/inference labels.
        for n,claim in enumerate(statements[1:],2):
            body+='<article class="cb-judgment"><button class="cb-toggle" aria-expanded="false" aria-controls="cb-text-'+str(n)+'"><span>'+bi('判断 '+str(n),'View '+str(n))+'</span><span class="cb-toggle-label">'+bi('展开','Expand')+'</span><span class="cb-chevron" aria-hidden="true">⌄</span></button><div class="cb-text" id="cb-text-'+str(n)+'"><p>'+e(claim['text'])+'</p></div></article>'
        body+='</div><div class="cb-main-actions"><span>'+bi('判断保留原文；不代表最新行情','Original judgments; not a live market update')+'</span><a class="cb-primary" href="'+url+'">'+bi('阅读与编辑报告','Read and edit report')+'</a></div>'
    else:
        body+='<div class="cb-empty"><h3>'+bi('还没有可复核的判断','No judgment to review yet')+'</h3><p>'+bi('先查看已有材料，确定这家公司的研究问题。','Start with the source materials and define the research question.')+'</p><a href="'+base+'/materials">'+bi('查看原始材料','Open source materials')+'</a></div></div>'
    body+='</section><aside class="research-support"><section class="cb-context"><h2>'+bi('报告信息','Report context')+'</h2>'
    if featured:
        status={'candidate':('待审核','Pending review'),'adopted':('已采纳','Adopted'),'draft':('草稿','Draft'),'rejected':('已拒绝','Rejected'),'archived':('已归档','Archived')}.get(featured.get('status'),('待确认','Unconfirmed'))
        fields=[(('作者','Author'),featured.get('researcher_label') or featured.get('researcher_id') or '—'),(('报告日期','Report date'),str(featured.get('created_at') or featured.get('run_started_at') or '')[:10]),(('依据材料','Based on'),featured.get('primary_title') or featured.get('primary_document_id') or ''),(('版本','Revision'),str(featured.get('revision') or ''))]
        body+='<span class="cb-status">'+bi(*status)+'</span><dl>'
        for label,value in fields:body+='<dt>'+bi(*label)+'</dt><dd>'+e(value)+'</dd>'
        body+='</dl><p class="cb-meta">'+bi('报告日期不同于材料覆盖期；尚未生成近期表现简报。','Report date differs from source coverage; a recent-performance brief is not yet available.')+'</p>'
    else:body+='<p class="cb-meta">'+bi('暂无报告记录。','No report recorded.')+'</p>'
    body+='</section><section class="cb-context"><h2>'+bi('研究依据','Research evidence')+'</h2><a class="cb-resource" href="'+base+'/materials"><span>'+bi('原始材料','Materials')+'</span><span>'+str(len(docs))+'</span></a><a class="cb-resource" href="'+base+'/data"><span>'+bi('结构化数据','Structured data')+'</span><span>'+(bi('候选','Candidate') if bundle else bi('未生成','Unavailable'))+'</span></a><p class="cb-meta">'+(bi('FY2025 候选数据，待审核。','FY2025 candidate data, pending review.') if bundle else bi('尚未生成结构化数据。','No structured data yet.'))+'</p></section><details class="cb-archive"><summary>'+bi('研究档案','Research archive')+' <span>'+str(len(groups))+'</span></summary>'+report_list(rows)+'</details></aside></div>'
    body+='<style>'+asset_text('company_brief.css')+'</style><script>'+asset_text('company_brief.js')+'</script>'
    return page(company['name'],body)
