"""Company research snapshots: deliberately small, server-rendered review UI.

The UI is not an authority for adoption eligibility. The archive store must
repeat all status, version, and exclusivity checks on every POST.
"""
from datetime import datetime
from html import escape
import json
import hashlib
from pathlib import Path
import re
from urllib.parse import quote, urlencode, urlsplit
from zoneinfo import ZoneInfo
from apps.review_workbench.citation_translations import translated_quote
from apps.review_workbench.visual_system import workbench_page
from apps.review_workbench.report_text import render_report, report_outline


def e(value):
    return escape(str(value if value is not None else ""), quote=True)


def bi(zh, en):
    return f'<span lang="zh">{e(zh)}</span><span lang="en">{e(en)}</span>'


def _url(value):
    value = str(value or "")
    parts = urlsplit(value)
    if parts.scheme in {"http", "https"} or (value.startswith("/") and not value.startswith("//")):
        return e(value)
    return ""


def _time(value):
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return str(value) + " (timezone unknown)"
        return parsed.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(value)


def _text(value):
    if isinstance(value, dict):
        return value.get("text") or value.get("message") or value.get("description") or json.dumps(value, ensure_ascii=False)
    return str(value or "")


def _material_time(snapshot, key="material_available_at"):
    """Do not turn date-only import placeholders into precise release times."""
    value = snapshot.get(key)
    if snapshot.get("material_time_precision") == "date":
        return str(value)[:10] if value else "—"
    return _time(value)


def _list(values):
    if not values:
        return '<p class="muted">' + bi("本次运行未提供，不代表不存在。", "Not supplied by this run; absence is not evidence.") + '</p>'
    if not isinstance(values, list):
        values = [values]
    return '<ul class="prose-list">' + ''.join('<li>' + e(_text(v)) + '</li>' for v in values) + '</ul>'


STATUS = {
    "candidate": ("待批阅", "Pending review"), "draft": ("待批阅", "Pending review"),
    "adopted": ("已采纳", "Adopted"), "archived": ("已归档", "Archived"),
    "deleted": ("已删除", "Deleted"), "rejected": ("已拒绝", "Rejected"),
}


def _badge(status):
    return f'<span class="badge status-{e(status)}">' + bi(*STATUS.get(status, (status, status))) + '</span>'


def _material_label(citation, documents):
    doc = documents.get(citation.get('document_id'), {})
    period, form = str(doc.get('period_end') or ''), str(doc.get('form') or '')
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', period) and form:
        if form in {'10-Q', '10-Q/A'} and period[5:] in {'03-31', '06-30', '09-30', '12-31'}:
            return f'{period[:4]} Q{int(period[5:7]) // 3} {form}'
        if form in {'10-K', '10-K/A'}:
            return f'{period[:4]} {form}'
        return f'{period} {form}'
    return str(doc.get('title') or citation.get('document_title') or '材料名称待核对 / Source unidentified')


def _citation_excerpt(citation):
    # Display the recorded citation, not a newly invented explanation of it.
    value = re.sub(r'\s+', ' ', str(citation.get('quote') or '')).strip().strip('“”"')
    if not value:
        kind = citation.get('type') or citation.get('block_type')
        return ('图表数据（未提供文字摘录） / Chart data (no text excerpt)'
                if kind in {'image', 'chart'} else '未提供引用摘录 / Excerpt unavailable')
    if len(value) <= 64:
        return value
    end = value.rfind(' ', 40, 64)
    return value[:end if end > 0 else 64].rstrip() + '…'


def _claims(answer, documents=None):
    if isinstance(answer, dict) and 'report_markdown' in answer:
        return render_report(answer['report_markdown'])
    documents = documents or {}
    claims = answer.get("claims", []) if isinstance(answer, dict) else []
    if not claims:
        return '<div class="prose">' + e(_text(answer)) + '</div>' if answer else '<p>' + bi("本次没有可展示的答案。", "No answer was produced.") + '</p>'
    rows = []
    for n, claim in enumerate(claims, 1):
        if not isinstance(claim, dict):
            claim = {"text": str(claim)}
        citations = []
        seen = set()
        for citation in claim.get("citations", []):
            if not isinstance(citation, dict):
                continue
            href = _url(citation.get("url") or citation.get("source_url"))
            identity = tuple(str(citation.get(key) or '') for key in ('document_id', 'index_id', 'block_id', 'quote'))
            if identity in seen:
                continue
            seen.add(identity)
            excerpt, material = _citation_excerpt(citation), _material_label(citation, documents)
            title = material + '：' + excerpt
            zh = translated_quote(citation)
            zh_excerpt = (zh[:24].rstrip() + '…') if len(zh) > 24 else zh
            label = bi(zh_excerpt, excerpt) if zh else e(excerpt)
            zh_title = material + '：' + (zh_excerpt or '译文待补 · ' + excerpt)
            link = (f'<a class="evidence-text" href="{href}" data-source="{href}" data-source-title="{e(title)}" data-source-title-zh="{e(zh_title)}" data-quote-zh="{e(zh)}" title="{e(citation.get("quote") or excerpt)}">{label}</a>' if href else f'<span>{label} ({bi("定位链接缺失", "Link unavailable")})</span>')
            missing = '' if zh else '<span lang="zh" class="translation-missing">待译</span>'
            citations.append('<span class="citation">' + link + ' <span class="material-label">[' + e(material) + ']</span>' + missing + '</span>')
        claim_type = claim.get("kind") or claim.get("type") or claim.get("claim_type")
        tag = f'<small>{e(claim_type)}</small>' if claim_type else ''
        separator = '<span class="citation-separator">；</span>'
        visible = separator.join(citations[:3])
        if len(citations) > 3:
            extra_id = f'claim-{n}-more-citations'
            visible += f'<span id="{extra_id}" class="extra-citations" hidden>' + separator + separator.join(citations[3:]) + '</span>'
            visible += f' <button type="button" class="citation-toggle" aria-expanded="false" aria-controls="{extra_id}"><span class="more-label">' + bi('展开更多', 'Show more') + '</span><span class="less-label" hidden>' + bi('收起', 'Show less') + '</span></button>'
        basis = '<div class="citations"><span class="basis-label">' + bi('基于：', 'Based on: ') + '</span>' + visible + '</div>' if citations else ''
        claim_text = claim.get('text', '')
        text_hash = hashlib.sha256(claim_text.encode()).hexdigest()
        rows.append(f'<article class="claim" id="claim-{n}"><div>{tag}<div class="prose" data-annotatable="{n}" data-text-hash="{text_hash}">{e(claim_text)}</div>' + basis + '</div></article>')
    return ''.join(rows)


@workbench_page('research')
def render_archive(company, snapshots, selected_id=None, documents=None, researcher_id=None, scope=None, material_id=None, active_section="reports"):
    """Render the archive without mutating or implicitly adopting a result."""
    company_id = company.get("id", "alphabet") if isinstance(company, dict) else str(company)
    company_name = company.get("name", company_id) if isinstance(company, dict) else str(company)
    route = '/companies/' + quote(company_id, safe='') + '/reports'
    from .archive_navigation import navigation, revision_history, editor_label
    from .site_navigation import company_tabs
    nav = navigation(snapshots, selected_id, researcher_id, scope, material_id, route, bi, _badge, _time, documents)
    rows, selected = nav['rows'], nav['selected']
    selected_id = selected.get("id") if selected else None
    timeline = [nav['agents']]
    content = '<div class="empty">' + bi("暂无研究快照。不会自动发起模型调用。", "No research snapshots. No model call is started automatically.") + '</div>'
    client = {"route": route, "selected": None, 'researcher_id': nav['researcher_id'], 'scope': nav['scope']}
    if selected:
        s = selected
        status = s.get("status", "candidate")
        answer = s.get("answer") or {}
        if not isinstance(answer, dict):
            answer = {"text": answer}
        group = [r for r in rows if r.get("scope") == s.get("scope") and r.get("primary_document_id") == s.get("primary_document_id") and r["id"] != s["id"]]
        candidates = [r for r in group if r.get("status") in {"candidate", "draft"}]
        effective = next((r for r in group if r.get('status') == 'adopted'), None)
        occupied = effective is not None
        can_adopt = s.get("validation_status") == "passed" and s.get('researcher_id', 'unassigned') != 'unassigned'
        buttons = []
        parent = next((r for r in rows if r.get("id") == s.get("parent_snapshot_id")), {})
        can_review = (s.get("edit_kind") in {"human_revision", "agent_revision"} and s.get("validation_status") == "pending"
                      and status in {"candidate", "archived"} and parent.get("validation_status") == "passed"
                      and not s.get("citation_errors"))
        if can_review:
            buttons.append('<button data-action="review">' + bi("审核修订", "Review revision") + '</button>')
        if status in {"candidate", "draft", "archived"}:
            reason = bi("证据校验或研究者身份未通过，不能跳过。", "Evidence checks or researcher identity unresolved.")
            buttons.append('<button class="primary" data-action="adopt"' + ('' if can_adopt else ' disabled') + '>' + bi("采纳整份报告", "Adopt report") + '</button>')
            if not can_adopt:
                buttons.append('<span class="muted action-hint">' + reason + '</span>')
            buttons.append('<button data-open="inline-report">' + bi("编辑报告", "Edit report") + '</button>')
        if status in {"candidate", "draft", "adopted"}:
            buttons.append('<button data-action="archive">' + bi("归档", "Archive") + '</button>')
        if status in {"candidate", "draft", "archived"}:
            buttons.append('<button data-action="delete">' + bi("删除", "Delete") + '</button>')
        if status == 'adopted' or status == 'rejected':
            buttons.append('<button data-open="inline-report">' + bi('编辑报告', 'Edit report') + '</button>')
        if status == 'candidate':
            buttons.append('<button data-action="reject">' + bi('拒绝', 'Reject') + '</button>')
        if status == 'rejected':
            buttons.append('<button data-action="reconsider">' + bi('重新审核', 'Reconsider') + '</button><button data-action="delete">'+bi('删除','Delete')+'</button>')
        if status == "deleted":
            buttons.append('<button data-action="restore">' + bi("恢复为归档", "Restore as archived") + '</button>')
        scope_title = bi("公司增长驱动与风险", "Company growth drivers & risks") if s.get("scope") == "company-drivers" else e(s.get("scope", ""))
        question = str(s.get("question") or '')
        short_question = question.split('？', 1)[0] + '？' if '？' in question else question.splitlines()[0] if question else ''
        heading = e(short_question[:120]) if short_question else scope_title
        mode_label = '<span class="badge">' + e(s.get("mode", "")) + '</span>' if s.get("mode") else ''
        header = '<div class="detail-heading" id="analysis-report"><div><div class="eyebrow">' + scope_title + '</div><h1>' + heading + '</h1><div class="report-state">' + mode_label + '</div></div></div>'
        date_only = s.get("material_time_precision") == "date"
        meta = '<dl class="metadata">' + ''.join('<div><dt>' + bi(zh, en) + '</dt><dd>' + e(val) + '</dd></div>' for zh, en, val in [
            ("内容作者", "Content author", s.get("author") or "未记录 / Not recorded"),
            ("主材料", "Primary source", s.get("primary_title") or s.get("primary_document_id", "—")),
            ("材料公开日期 · 具体时间未知" if date_only else "材料公开时间", "Publication date · exact time unknown" if date_only else "Material published", _material_time(s)),
            ("本次材料日期边界 · 仅日期" if date_only else "本次信息截止", "Material date boundary · date only" if date_only else "Knowledge cutoff", _material_time(s, "knowledge_cutoff_at") if s.get("knowledge_cutoff_at") else _time(s.get("knowledge_cutoff"))),
            ("运行版本 · 上海时间", "Run version · Shanghai", _time(s.get("run_started_at")) + ' · ' + s["id"][-8:] + ' · r' + str(s.get("revision", 1))),
        ]) + '</dl>'
        notices = '<details class="notice"><summary>' + bi('使用说明与当前限制', 'Usage & current limitations') + '</summary><p>' + bi('档案功能试用版：上下文筛选已实现；尚未连接下一轮模型执行，人工意见仍待系统重审。', 'Archive pilot: context eligibility is implemented; next-run model integration and opinion re-review are not yet active.') + '</p></details>'
        if s.get('edit_kind'):
            notices += '<p class="notice">'+editor_label(s, bi)+' · '+bi('修订时间：','Edited at: ')+e(_time(s.get('edited_at') or s.get('created_at')))+' · <a href="'+e(route+'?'+urlencode({'tab':'research','snapshot':s.get('parent_snapshot_id')}))+'">'+bi('查看修改前版本','View parent version')+'</a></p>'
        if s.get("primary_inferred"):
            notices += '<p class="notice">' + bi("历史运行未指定主材料，此处按读取记录推定；采纳时需确认，不代表原运行已按此冻结。", "The original run did not declare a primary source. This is inferred from reading records and must be confirmed on adoption.") + '</p>'
        if s.get("validation_status") != "passed":
            notices += '<p class="notice warning">' + bi("证据校验未通过：可审核思路、记录意见，但不能采纳为后续基线。", "Evidence validation failed: review and comment are allowed, but adoption as context is blocked.") + '</p>'
        if status == "adopted":
            notices += '<p class="notice">' + bi("生效内容只读；可派生修订，采纳新修订后再替换。采纳不代表事实正确。", "Effective content is read-only. Derive a revision without withdrawing it; replace after review.") + '</p>'
        if status in {"archived", "deleted"}:
            notices += '<p class="notice">' + bi("此版本不进入后续默认上下文；过去运行的记录不会被重写。", "Excluded from future default context. Past run manifests remain unchanged.") + '</p>'
        if s.get("needs_review") or s.get("lineage_review_required") or s.get("inheritance_review_required"):
            notices += '<p class="notice warning">' + bi("继承来源或意见发生变化，需要复核。", "Inherited sources or opinions changed; review required.") + '</p>'
        baseline = s.get("baseline_snapshot_id")
        if baseline:
            diff = '<p>' + bi("相对基线", "Compared with baseline") + f' <a href="{e(route + "?" + urlencode({"tab": "research", "snapshot": baseline}))}">{e(baseline)}</a></p>' + _list(s.get("changes") or s.get("diff"))
        else:
            diff = '<p class="muted">' + bi("本次运行未记录基线；展示原始研究，不推造与上一版的业务变化。", "No baseline was recorded. No change in the business is inferred from another run.") + '</p>'
        human_notes = '<section><h2>' + bi("人工修订说明", "Human revision notes") + '</h2><div class="prose">' + e(s.get("human_notes")) + '</div><p class="muted">' + bi("此内容来自人工，不覆盖下方模型原始答案，也不自动修复引用。", "Human-authored notes do not overwrite the model answer or repair citations automatically.") + '</p></section>' if s.get("human_notes") else ''
        comments = []
        for comment in s.get("comments", []):
            cid = comment.get("id") or comment.get("opinion_id") or comment.get("comment_id")
            withdrawn = bool(comment.get("withdrawn") or comment.get("status") == "withdrawn" or comment.get("withdrawn_at"))
            carrying = bool(comment.get("carry_forward")) and not withdrawn
            control = f'<button data-action="withdraw_opinion" data-opinion="{e(cid)}">' + bi("撤回意见", "Withdraw opinion") + '</button>' if not withdrawn and cid and status != "deleted" else ''
            feedback_label = ('<p class="muted">'+bi('点赞' if comment.get('feedback_vote')=='up' else '点踩','Like' if comment.get('feedback_vote')=='up' else 'Dislike')+' · '+e(comment.get('block_id'))+'</p>') if comment.get('feedback_vote') else ''
            comments.append('<article class="opinion">'+feedback_label+'<div class="row"><small>' + e(comment.get("kind", "")) + ' · ' + e(_time(comment.get("created_at"))) + ' · ' + bi("已撤回" if withdrawn else "请求带入后续" if carrying else "仅本次意见", "Withdrawn" if withdrawn else "Carry-forward requested" if carrying else "This review only") + '</small>' + control + '</div>' + ('<blockquote class="opinion-quote">' + e(comment['source_selection']['quote']) + '</blockquote>' if comment.get('source_selection') else '') + '<div class="prose">' + e(comment.get("text", "")) + '</div><small>' + bi("系统审查", "System review") + ': ' + e(comment.get("review_status") or "not_reviewed") + '</small>' + ('<p>' + e(comment.get("review_reason", "")) + '</p>' if comment.get("review_reason") else '') + '</article>')
        comment_form = '' if status == "deleted" else '''<form id="opinion-form"><label for="opinion-text">''' + bi("写下你的意见", "Your review") + '''</label><textarea id="opinion-text" name="text" required rows="3" maxlength="12000"></textarea><div class="form-row"><label>''' + bi("意见类型", "Type") + ''' <select name="kind"><option value="preference">研究偏好 / Preference</option><option value="fact_claim">事实主张 / Factual claim</option><option value="hypothesis">投资假设 / Hypothesis</option></select></label><label><input type="checkbox" name="carry_forward"> ''' + bi("带入后续分析", "Carry into future analysis") + '''</label><button type="submit">''' + bi("保存意见", "Save review") + '''</button></div></form>'''
        opinions = '<section><h2>' + bi("人工意见与后续继承", "Human review & inheritance") + '</h2><p class="muted">' + bi("意见不是事实。类型由你指定，系统尚未复核时会明确标记；同版重跑可以使用未采纳报告上的意见；跨材料继承仍遵守采纳与时间规则，每次须重新审查。", "Opinions are not facts. Your selected type remains unreviewed until checked. Same-report reruns may use unadopted feedback; inheritance across materials requires adoption and time eligibility. Every run must review it.") + '</p>' + ''.join(comments) + comment_form + '</section>'
        links = []
        for key, zh, en in [("experiment_url", "原实验与费用", "Original experiment & cost"), ("source_url", "主材料原文", "Primary source")]:
            href = _url(s.get(key))
            if href:
                links.append(f'<a href="{href}" target="_blank" rel="noopener">' + bi(zh, en) + ' ↗</a>')
        trace = '<details class="run-details"><summary>' + bi("运行与审核记录", "Run & audit details") + '</summary><div class="links">' + ''.join(links) + '</div><dl class="metadata"><div><dt>Run ID</dt><dd>' + e(s.get("run_id", "—")) + '</dd></div><div><dt>Snapshot ID</dt><dd>' + e(s["id"]) + '</dd></div><div><dt>' + bi("证据校验", "Evidence validation") + '</dt><dd>' + e(s.get("validation_status", "unknown")) + '</dd></div></dl>' + _list(s.get("validation_errors") or s.get("citation_errors")) + '</details>'
        buttons.append('<a class="history-jump" href="#revision-history">'+bi('修订历史', 'Revision history')+'</a>')
        buttons = [b for b in buttons if 'data-open=' not in b]
        primary_buttons = [b for b in buttons if 'data-action="review"' in b]
        other_buttons = [b for b in buttons if b not in primary_buttons]
        toolbar = '<div class="report-toolbar" data-editor-version="inline-v2"><div class="read-actions">'+''.join(primary_buttons)+'<details class="more-actions"><summary>'+bi('更多','More')+'</summary><div>'+''.join(other_buttons)+'</div></details></div><div class="edit-actions" hidden><button id="save-inline" class="primary">'+bi('保存修订','Save revision')+'</button><button id="cancel-inline">'+bi('取消','Cancel')+'</button><input id="inline-reason" aria-label="Revision reason" placeholder="修改说明 / Revision note" maxlength="20000"><span id="edit-state" role="status"></span></div></div>'
        content = toolbar + header + meta + notices + nav['versions'] + human_notes + '<section><h2>' + (bi('研究报告', 'Research report') if answer.get('report_markdown') else bi('当前判断', 'Current judgment')) + '</h2>' + _claims(answer, documents) + '</section><section><h2>' + bi("相对基线改变了什么", "What changed from the baseline") + '</h2>' + diff + '</section><section><h2>' + bi("未知项与材料限制", "Unknowns & limitations") + '</h2>' + _list(answer.get("limitations")) + '</section><section><h2>' + bi("核查发现与验证线索", "Findings & verification leads") + '</h2>' + _list(answer.get("findings")) + '</section>' + opinions + trace
        if answer.get('report_markdown'):
            content = toolbar + header + meta + notices + nav['versions'] + human_notes + _claims(answer, documents) + opinions + trace
        from uteki.agents.review_blocks import review_blocks, valid_decisions
        client['blocks'] = review_blocks(s.get('answer'))
        client['block_decisions'] = valid_decisions(s)
        client["selected"] = {"id": s["id"], "revision": s.get("revision", 1), "primary_inferred": s.get("primary_inferred", False), "competitors": [r.get("label") or r["id"] for r in candidates], "human_notes": s.get("human_notes", "")}
        if question:
            content += '<details class="run-details"><summary>' + bi('完整研究问题与要求', 'Full research query') + '</summary><div class="prose">' + e(question) + '</div></details>'
        client['selected']['status'] = status
        client['selected'].update(answer=answer, material_id=s['primary_document_id'], slot_revision=s.get('slot_revision'),
                                  effective={'id': effective['id'], 'revision': effective['revision']} if effective else None)
    else:
        content = nav['versions'] + content
    left_panel = '<h2>'+bi('分析报告','Reports')+'</h2>'+nav['researcher_control']+'<nav class="report-choices" aria-label="Reports">'+nav['report_links']+'</nav>'
    advanced = '<details class="archive-options"><summary>'+bi('版本与研究设置','Versions & research settings')+'</summary>'+nav['controls']+'<label>'+bi('版本状态','Version status')+'<select id="version-status"><option value="all" data-zh="全部" data-en="All">全部</option><option value="candidate" data-zh="待审核" data-en="Pending">待审核</option><option value="adopted" data-zh="已采纳" data-en="Adopted">已采纳</option></select></label><label><input type="checkbox" id="show-deleted">'+bi('显示已删除历史','Show deleted history')+'</label>'+nav['timeline']+'</details>'
    source = (documents or {}).get(selected.get('primary_document_id'), {}) if selected else {}
    right_panel = '<h2>' + bi('原始材料快照', 'Source snapshot') + '</h2>'
    if selected:
        right_panel += '<dl class="snapshot-facts">' + ''.join('<dt>' + bi(zh,en) + '</dt><dd>' + e(value) + '</dd>' for zh,en,value in [
            ('材料','Material',selected.get('primary_title') or selected.get('primary_document_id')),
            ('公开日期','Published',_material_time(selected)),
            ('材料标识','Document ID',selected.get('primary_document_id')),
            ('内容指纹（目录记录）','Content hash (catalog)',source.get('sha256') or '未记录 / Not recorded'),
            ('索引版本（目录记录）','Index version (catalog)',source.get('index_folder') or '未记录 / Not recorded')]) + '</dl>'
        right_panel += '<p class="muted">' + bi('目录信息用于定位材料；不代表本次运行冻结了该目录版本。运行依据见审核记录。','Catalog metadata locates the source; it does not certify this run used that catalog version. See run records.') + '</p>'
        href = _url(selected.get('source_url') or source.get('source_url'))
        if href:
            right_panel += '<a target="_blank" rel="noopener" href="'+href+'">'+bi('打开原始材料','Open original source')+'</a>'
        right_panel += report_outline(selected.get('answer'), bi)
    else:
        right_panel += '<p>'+bi('选择报告后显示关联材料。','Select a report to see its source.')+'</p>'
    material_panel = right_panel
    history_panel = (revision_history(selected, bi) if selected else '<p>'+bi('选择报告后查看修订。','Select a report to view revisions.')+'</p>') + advanced
    cross_panel = '<h2>'+bi('模型交叉 Review','Cross-model review')+'</h2><p class="cross-status">'+bi('尚未运行','Not run')+'</p><p>'+bi('固定整篇报告及证据版本，由其他 Agent 逐段检查。','Freeze the report and evidence versions for paragraph-by-paragraph review by other agents.')+'</p><ul><li>'+bi('事实与引用是否支持结论','Check facts and supporting citations')+'</li><li>'+bi('找出遗漏、反证与推理问题','Identify omissions, counterevidence and reasoning issues')+'</li><li>'+bi('每段展示意见、依据和修改建议','Show findings, evidence and suggested edits for each paragraph')+'</li></ul><p class="muted">'+bi('评审执行尚未接入。后续显示评审模型、时间及对应段落；模型意见不自动采纳正文。','Review execution is not connected yet. Results will identify reviewer model, time and paragraph; model feedback will not auto-accept content.')+'</p>'
    panels = [('materials','材料','Sources',material_panel),('revisions','修订','Revisions',history_panel),('cross-review','交叉 Review','Cross-review',cross_panel)]
    right_panel = '<div class="review-tabs" role="tablist" aria-label="Review sidebar">'+''.join('<button type="button" role="tab" id="tab-'+key+'" aria-controls="panel-'+key+'" aria-selected="'+str(i==0).lower()+'" tabindex="'+('0' if i==0 else '-1')+'" data-review-tab="'+key+'">'+bi(zh,en)+'</button>' for i,(key,zh,en,body) in enumerate(panels))+'</div>'
    right_panel += ''.join('<section role="tabpanel" id="panel-'+key+'" aria-labelledby="tab-'+key+'" '+('hidden' if i else '')+'>'+body+'</section>' for i,(key,zh,en,body) in enumerate(panels))
    payload = json.dumps(client, ensure_ascii=False).replace('<', '\\u003c')
    drawer = '<div id="source-drawer" role="dialog" aria-label="参考摘录 / Reference excerpt" hidden><div class="source-toolbar"><strong>' + bi("原文证据", "Source evidence") + '</strong><a id="source-new-tab" target="_blank" rel="noopener">' + bi("新窗口 ↗", "New tab ↗") + '</a><button id="close-source" aria-label="Close source">×</button></div><div id="source-caption"></div><div id="source-excerpt"></div></div>'
    return '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>''' + e(company_name) + ''' · Research Archive</title><style>''' + CSS + '''</style></head><body><header><a href="/companies">Uteki / ''' + bi("公司", "Companies") + '''</a><strong>''' + e(company_name) + '''</strong><button id="language">中文 / EN</button></header>''' + company_tabs(company_id, active_section) + '''<div id="feedback" role="status" hidden></div><main><aside class="report-list-rail">''' + left_panel + '''</aside><div class="detail"><div id="report-reading">''' + content + '''</div></div><div class="material-rail" role="complementary" aria-label="Source snapshot">''' + right_panel + '''</div></main>''' + drawer + '''<script type="application/json" id="archive-state">''' + payload + '''</script><script>''' + JS + '''</script></body></html>'''


CSS = '''
:root{
 --paper:#fff;--rail:#f1f4f8;--ink:#202b3b;--muted:#566477;
 --blue:#275dad;--line:#dce2eb;--selected:#e5edfa;--warning:#85531e;
 --ui:"Avenir Next","PingFang SC","Microsoft YaHei",sans-serif;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.6 var(--ui);-webkit-font-smoothing:antialiased}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
button,input,textarea,select{font:inherit;color:inherit}
button,select{border:1px solid #bfcad9;background:var(--paper);border-radius:6px;padding:7px 12px}
button{cursor:pointer;min-height:36px}button:hover:not(:disabled){background:var(--rail)}
button:disabled{cursor:not-allowed;color:#697687;background:#f0f2f5;border-color:#e0e5eb}
:focus-visible{outline:3px solid var(--blue);outline-offset:3px}
.primary{background:var(--blue);color:white;border-color:var(--blue)}
.primary:hover:not(:disabled){background:#204e93}
header{display:flex;align-items:center;gap:26px;padding:14px 28px;border-bottom:1px solid var(--line);min-height:62px}
header>a{font-weight:600}header>strong{font-size:19px;letter-spacing:-.4px}header button{margin-left:auto}
nav{display:flex;gap:26px;padding:0 28px;border-bottom:1px solid var(--line)}
nav a{padding:13px 0;color:var(--muted)}nav a.active{color:var(--blue);box-shadow:inset 0 -3px var(--blue);font-weight:600}
main{display:grid;grid-template-columns:268px minmax(0,1fr);min-height:calc(100vh - 113px)}
aside{background:var(--rail);border-right:1px solid var(--line);padding:22px 12px;min-width:0}
.sidebar-heading,.row,.detail-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}
.sidebar-heading{padding:0 10px}.sidebar-heading strong{font-size:15px}.sidebar-heading label{font-size:12px}
.compact{font-size:12px;padding:0 10px;color:var(--muted);line-height:1.65}
.group-title{font-weight:600;font-size:12px;padding:23px 10px 9px}
.group-title small{font-weight:400;margin-top:5px;font-size:11px}
.timeline-group{padding:0;margin:0;border:0}
.snapshot{display:block;padding:11px 12px;margin:3px 0;border-radius:7px;color:inherit;border:1px solid transparent}
.snapshot.selected{background:var(--paper);border-color:#b5c9e8;box-shadow:inset 3px 0 var(--blue)}
.snapshot:hover{background:#e6ecf5;text-decoration:none}
.snapshot.selected:hover{background:var(--paper)}
.snapshot .row strong{font-size:14px;font-weight:600}
.snapshot small{font-size:11px}
.snapshot[data-deleted=true]{display:none}.show-deleted .snapshot[data-deleted=true]{display:block}
.version{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums;margin:5px 0 1px}
.badge{display:inline-flex;align-items:center;font-size:11px;font-weight:500;padding:2px 7px;border-radius:4px;background:#edf1f6;color:#46566c;white-space:nowrap}
.status-adopted{color:#205d45;background:#e1f0e8}
.status-archived,.status-deleted{color:#5d6673;background:#e8ebef}
.detail{padding:30px clamp(24px,3.5vw,60px) 80px;min-width:0}
.detail-heading{align-items:flex-start;gap:20px}
.detail-heading h1{font-size:clamp(23px,2.1vw,31px);font-weight:600;letter-spacing:-.6px;line-height:1.4;margin:0 0 14px;max-width:34em}
.eyebrow{display:none}
.metadata{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px 28px;font-size:12px;margin:20px 0;padding:14px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);max-width:880px}
.metadata dt{color:var(--muted)}.metadata dd{margin:2px 0;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.notice{font-size:12px;line-height:1.65;color:var(--muted);padding:0;margin:9px 0;max-width:90ch}
.warning{color:var(--warning);border-left:3px solid #bc8749;background:#fff8ee;padding:10px 13px}
.actions{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:22px 0}
.action-hint{font-size:12px;max-width:220px;line-height:1.4}
h2{font-size:17px;line-height:1.5;font-weight:600;margin:0 0 12px}
section{margin-top:32px;padding-top:23px;border-top:1px solid var(--line)}
.claim{padding:17px 0 20px;border-bottom:1px solid #e8ecf2}
.claim:first-of-type{padding-top:3px}
.claim-number{display:none}
.prose{font-size:15px;line-height:1.85;white-space:pre-wrap;overflow-wrap:anywhere;max-width:76ch}
.citations{display:block;margin-top:12px;max-width:82ch;font-size:13px;line-height:1.9;overflow-wrap:anywhere}
.citation{display:inline-flex;align-items:baseline;gap:4px;max-width:100%;vertical-align:bottom}
.evidence-text{display:inline-block;max-width:min(28ch,45vw);min-width:0;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;vertical-align:bottom;text-decoration:underline;text-decoration-color:#b6c9e5;text-underline-offset:3px}
.evidence-text:hover{text-decoration-color:var(--blue)}
.translation-missing{color:var(--muted);font-size:10px;white-space:nowrap}
#citation-preview{position:fixed;z-index:20;width:min(480px,calc(100vw - 24px));max-height:min(320px,45vh);overflow:auto;overscroll-behavior:contain;padding:14px 16px;background:var(--paper);border:1px solid #bfcad9;border-radius:6px;box-shadow:0 6px 24px #202b3b20;font-size:13px;line-height:1.7;white-space:pre-wrap;overflow-wrap:anywhere}
#citation-preview[hidden]{display:none}
.basis-label,.citation-separator{color:var(--muted)}
.extra-citations[hidden],.citation-toggle [hidden]{display:none!important}
.citation-toggle{border:0;background:transparent;color:var(--blue);padding:2px 5px;min-height:28px;font-size:13px;text-decoration:underline;text-underline-offset:3px}
.citation-toggle:hover:not(:disabled){background:var(--rail)}
.material-label{display:inline;color:#46566c;font-size:12px;white-space:nowrap;background:#f1f4f8;border-radius:3px;padding:1px 4px}
.external-source{padding-left:5px}
.prose-list{padding-left:20px;max-width:80ch}.prose-list li{padding:5px 0;white-space:pre-wrap;overflow-wrap:anywhere}
.muted,small{color:var(--muted)}small{display:block;font-size:12px}
.opinion{padding:14px 0;border-bottom:1px solid var(--line)}.opinion button{font-size:12px}
textarea{display:block;width:100%;resize:vertical;padding:12px;border:1px solid #bfcad9;border-radius:6px;background:var(--paper);margin:9px 0}
#opinion-form{margin-top:20px;max-width:850px}.form-row{display:flex;flex-wrap:wrap;gap:15px;align-items:center}.form-row label{font-size:12px}
input[type=checkbox]{accent-color:var(--blue)}
.run-details{border-top:1px solid var(--line);margin-top:26px;padding-top:16px;font-size:13px}
.run-details summary{cursor:pointer;font-weight:500}.links{display:flex;gap:20px;margin:15px 0}
.empty{padding:70px 20px;color:var(--muted)}
dialog{width:min(90vw,680px);padding:28px;border:1px solid #bdc8d8;border-radius:10px;color:var(--ink)}
dialog::backdrop{background:#202b3b55}
#feedback{padding:12px 28px;background:#fff8ee;color:var(--warning);white-space:pre-wrap}
#source-drawer[hidden]{display:none}
#source-drawer{position:fixed;inset:0 0 0 auto;width:49vw;z-index:10;background:var(--paper);box-shadow:-4px 0 24px #202b3b18;display:flex;flex-direction:column;border-left:1px solid var(--line)}
.source-toolbar{display:flex;gap:14px;align-items:center;padding:13px 18px;border-bottom:1px solid var(--line)}
.source-toolbar a{margin-left:auto;font-size:12px}
#source-caption{padding:9px 18px;background:var(--rail);color:var(--muted);font-size:11px;overflow-wrap:anywhere}
#source-frame{width:100%;flex:1;border:0;min-height:0}
.source-open main{margin-right:49vw;grid-template-columns:200px minmax(0,1fr)}
.source-open .detail{padding:24px 20px}.source-open .metadata{grid-template-columns:1fr}
[lang=en]{display:none}html[data-language=en] [lang=en]{display:inline}html[data-language=en] [lang=zh]{display:none}
@media(min-width:561px){
 body{height:100vh;height:100dvh;display:flex;flex-direction:column;overflow:hidden}
 body>header,body>nav,body>#feedback{flex-shrink:0}
 main{flex:1;min-height:0;overflow:hidden}
 main>aside,main>.detail{min-height:0;overflow:auto;overscroll-behavior-y:contain}
}
@media(min-width:1600px){.detail{padding-right:7vw}.source-open .detail{padding-right:20px}}
@media(max-width:1150px){.source-open main{margin-right:0;grid-template-columns:268px minmax(0,1fr)}#source-drawer{width:65vw}}
@media(max-width:800px){main,.source-open main{grid-template-columns:210px minmax(0,1fr)}.detail{padding:24px 20px}.metadata{grid-template-columns:1fr}.snapshot .row{flex-wrap:wrap;gap:5px}}
@media(max-width:560px){main,.source-open main{display:block}aside{max-height:265px;overflow:auto;border-right:0;border-bottom:1px solid var(--line)}header{padding:12px 16px;gap:16px}nav{padding:0 16px}.detail{padding:24px 18px}.detail-heading h1{font-size:24px}#source-drawer{width:100vw}.source-toolbar{padding:10px 12px}.metadata{font-size:12px}.prose{font-size:14px}button{min-height:40px}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{scroll-behavior:auto!important;animation:none!important;transition:none!important}}
'''


JS = '''
const state=JSON.parse(document.getElementById('archive-state').textContent);
document.getElementById('researcher-filter')?.addEventListener('change',event=>{const u=new URL(state.route,location.origin);u.searchParams.set('researcher',event.target.value);location.assign(u.href)});
const lang=()=>document.documentElement.dataset.language||'zh';
const tr=(zh,en)=>lang()==='en'?en:zh;
document.querySelectorAll('#scope-filter').forEach(el=>el.onchange=()=>{
 const u=new URL(state.route,location.origin);u.searchParams.set('tab','research');
 u.searchParams.set('researcher',state.researcher_id);
 u.searchParams.set('scope',document.getElementById('scope-filter').value);
 if(state.selected?.material_id)u.searchParams.set('material',state.selected.material_id);
 location.assign(u.href);
});
document.documentElement.dataset.language=localStorage.getItem('data-language')||'zh';
document.getElementById('language').onclick=()=>{const l=lang()==='en'?'zh':'en';document.documentElement.dataset.language=l;localStorage.setItem('data-language',l);closeSource();const caption=document.getElementById('source-caption');caption.textContent=caption.dataset[l]||''};
const showDeleted=document.getElementById('show-deleted');
showDeleted.checked=new URLSearchParams(location.search).get('deleted')==='1'||state.selected?.status==='deleted';
function toggleDeleted(){document.body.classList.toggle('show-deleted',showDeleted.checked);const u=new URL(location.href);if(showDeleted.checked)u.searchParams.set('deleted','1');else u.searchParams.delete('deleted');history.replaceState(null,'',u)}
showDeleted.onchange=toggleDeleted;toggleDeleted();
const versionFilter=document.getElementById('version-status');
const localizeVersions=()=>versionFilter.querySelectorAll('option').forEach(option=>option.textContent=option.dataset[lang()]||option.dataset.zh);
localizeVersions();document.getElementById('language').addEventListener('click',localizeVersions);
versionFilter.onchange=()=>document.querySelectorAll('.version-row').forEach(row=>row.hidden=versionFilter.value!=='all'&&row.dataset.status!==versionFilter.value);
let busy=false;
async function mutate(action,extra={}){
 if(busy||!state.selected)return;busy=true;
 const feedback=document.getElementById('feedback');feedback.hidden=false;feedback.textContent=tr('正在保存…','Saving…');
 try{const response=await fetch('/api/research-archive',{method:'POST',headers:{'Content-Type':'application/json','X-Uteki-Request':'1'},body:JSON.stringify({snapshot_id:state.selected.id,action,expected_revision:state.selected.revision,...extra})});const result=await response.json();if(!response.ok||result.error)throw new Error(result.error||result.message||('HTTP '+response.status));
 const next=result.snapshot?.id||result.snapshot_id||result.selected_id||state.selected.id;const u=new URL(state.route,location.origin);u.searchParams.set('tab','research');u.searchParams.set('researcher',state.researcher_id);u.searchParams.set('scope',state.scope);u.searchParams.set('snapshot',next);if(showDeleted.checked||action==='delete')u.searchParams.set('deleted','1');location.assign(u.href);
 }catch(error){feedback.textContent=tr('未保存：','Not saved: ')+error.message+tr('。若版本已变化，请刷新后重试。','. If the revision changed, refresh before retrying.');busy=false;}
}
document.querySelectorAll('[data-action]').forEach(button=>button.onclick=()=>{
 const action=button.dataset.action;
 if(action==='adopt'){
  const current=state.selected.effective;
  const msg=(current?tr('替换当前生效版本？旧版将归档，其他候选保留。当前版本：','Replace the effective report? Its predecessor will be archived; other candidates stay pending. Current: ')+current.id:tr('采纳此版本作为本研究者的生效报告？','Adopt this version for this researcher?'))+(state.selected.primary_inferred?tr('\\n请同时确认推定主材料正确。','\\nConfirm the inferred primary source.'):'');
  if(confirm(msg))mutate(action,{confirm_primary:true,expected_slot_revision:state.selected.slot_revision,replace_snapshot_id:current?.id,replace_revision:current?.revision});
 }else if(action==='review'){const notes=prompt(tr('请记录审核依据：确认人工修订没有引入无依据事实，也未掩盖反证。该操作不会自动采纳。','Record your review basis: confirm the notes introduce no unsupported facts and conceal no counterevidence. This does not adopt the revision.'));if(notes&&notes.trim())mutate(action,{review_notes:notes.trim()})}
 else if(action==='reject'){const reason=prompt(tr('拒绝原因（保留历史，不进入上下文）','Reason for rejection (history retained, excluded from context)'));if(reason?.trim())mutate(action,{reason:reason.trim()})}
 else if(action==='delete'){if(confirm(tr('软删除此快照？后续不会加载，可恢复为归档。','Soft-delete this snapshot? It will be excluded and can be restored as archived.')))mutate(action)}
 else if(action==='archive'){if(confirm(tr('归档后不再进入未来默认上下文。历史运行记录不变。确认？','Archive and exclude from future default context? Past run records stay unchanged.')))mutate(action)}
 else if(action==='withdraw_opinion'){if(confirm(tr('撤回此意见并停止后续继承？历史记录保留。','Withdraw and stop future inheritance? History is retained.')))mutate(action,{opinion_id:button.dataset.opinion})}
 else mutate(action);
});
let editing=false,editNodes=[],structuralDraft=null;
const editStatus=()=>document.getElementById('edit-state');
function inlineMarkdown(node){
 if(node.nodeType===3)return node.textContent;
 const t=[...node.childNodes].map(inlineMarkdown).join('');
 if(node.tagName==='STRONG'||node.tagName==='B')return '**'+t+'**';
 if(node.tagName==='A')return '['+t+']('+node.getAttribute('href')+')';
 if(node.tagName==='BR')return ' ';
 return t;
}
function stopEditing(restore){
 if(structuralDraft){if(structuralDraft.node)structuralDraft.node.remove();if(structuralDraft.removed)structuralDraft.removed.hidden=false;structuralDraft=null;}
 editNodes.forEach(({el,html})=>{if(restore)el.innerHTML=html;el.removeAttribute('contenteditable');el.onpaste=null;el.onkeydown=null;el.oninput=null});
 editing=false;document.querySelector('.edit-actions').hidden=true;document.querySelector('.read-actions').hidden=false;
 document.body.classList.remove('editing-report');
}
function startBlockEdit(target){
 if(editing||busy||feedbackOpen||state.selected?.status==='deleted')return;editing=true;
 editNodes=[{el:target,html:target.innerHTML}];
 editNodes.forEach(({el})=>{
  el.setAttribute('contenteditable','true');el.setAttribute('spellcheck','true');
  el.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();document.execCommand('insertText',false,' ')}};
  el.onpaste=e=>{e.preventDefault();document.execCommand('insertText',false,e.clipboardData.getData('text/plain').replace(/\\r?\\n/g,' '))};
  el.oninput=()=>{editStatus().textContent=tr('尚未保存','Unsaved')};
 });
 document.querySelector('.read-actions').hidden=true;document.querySelector('.edit-actions').hidden=false;
 document.getElementById('inline-reason').value='';editStatus().textContent=tr('直接修改正文','Edit directly in the report');
 document.body.classList.add('editing-report');target.focus();
}
const sidebarTabs=[...document.querySelectorAll('[data-review-tab]')];
function selectReviewTab(key){sidebarTabs.forEach(tab=>{const on=tab.dataset.reviewTab===key;tab.setAttribute('aria-selected',String(on));tab.tabIndex=on?0:-1;document.getElementById('panel-'+tab.dataset.reviewTab).hidden=!on})}
sidebarTabs.forEach((tab,i)=>{tab.onclick=()=>selectReviewTab(tab.dataset.reviewTab);tab.onkeydown=e=>{let next;if(e.key==='ArrowRight')next=(i+1)%sidebarTabs.length;else if(e.key==='ArrowLeft')next=(i+sidebarTabs.length-1)%sidebarTabs.length;else if(e.key==='Home')next=0;else if(e.key==='End')next=sidebarTabs.length-1;else return;e.preventDefault();sidebarTabs[next].click();sidebarTabs[next].focus()}});
document.querySelectorAll('a[href="#revision-history"]').forEach(link=>link.addEventListener('click',()=>selectReviewTab('revisions')));
const blockNodes=[...document.querySelectorAll('#report-reading [data-md-line],#report-reading .claim [data-annotatable]')];
const blockKey=el=>el.hasAttribute('data-md-line')?'md:'+el.dataset.mdLine+(el.hasAttribute('data-md-cell')?':'+el.dataset.mdCell:''):'claim:'+(Number(el.dataset.annotatable)-1);
const progress=document.createElement('span');progress.id='block-progress';progress.setAttribute('role','status');
document.querySelector('.report-toolbar')?.prepend(progress);
const accepted=k=>state.block_decisions?.[k]?.accepted===true;
const rejected=k=>state.block_decisions?.[k]?.decision==='rejected';
function updateProgress(){const keys=Object.keys(state.blocks||{}),n=keys.filter(k=>accepted(k)||rejected(k)).length;progress.textContent=keys.length&&n===keys.length?tr('已完成批阅','Review complete'):tr('已批阅（','Reviewed (')+n+'/'+keys.length+tr('）',')');blockNodes.forEach(el=>{const k=blockKey(el);el.dataset.accepted=String(accepted(k));el.dataset.rejected=String(rejected(k))})}
function updateDecisionButtons(){const k=hoveredBlock&&blockKey(hoveredBlock);acceptButton.textContent=tr('采纳','Accept');rejectButton.textContent=tr('拒绝','Reject');acceptButton.setAttribute('aria-pressed',String(accepted(k)));rejectButton.setAttribute('aria-pressed',String(rejected(k)))}
const blockActions=document.createElement('div');blockActions.id='block-actions';blockActions.hidden=true;
const acceptButton=document.createElement('button');acceptButton.type='button';blockActions.append(acceptButton);document.body.append(blockActions);
let hoveredBlock=null, hideBlockTimer=null;const actionSlots=new Map();
function cancelBlockHide(){clearTimeout(hideBlockTimer);hideBlockTimer=null}
function scheduleBlockHide(){if(feedbackOpen||hideBlockTimer||blockActions.contains(document.activeElement))return;hideBlockTimer=setTimeout(()=>{blockActions.classList.remove('actions-visible');hideBlockTimer=null},600)}
blockActions.addEventListener('mouseenter',()=>{cancelBlockHide();blockActions.classList.add('actions-visible')});
blockActions.addEventListener('mouseleave',scheduleBlockHide);
blockActions.addEventListener('focusin',cancelBlockHide);
blockActions.addEventListener('focusout',scheduleBlockHide);
let feedbackOpen=false;
function positionActions(el){const slot=actionSlots.get(el);if(slot&&blockActions.parentElement!==slot)slot.append(blockActions)}
function showBlockActions(el){if(editing||busy||feedbackOpen)return;cancelBlockHide();hoveredBlock=el;updateDecisionButtons();positionActions(el);blockActions.hidden=false;requestAnimationFrame(()=>blockActions.classList.add('actions-visible'))}
blockNodes.forEach(el=>{
 el.classList.add('review-block');el.tabIndex=0;
 const anchor=el.closest('.report-table')||el;
 let slot=anchor.nextElementSibling;
 if(!slot?.classList.contains('block-action-slot')){slot=document.createElement('div');slot.className='block-action-slot';anchor.after(slot)}
 actionSlots.set(el,slot);
 slot.addEventListener('mouseenter',()=>{cancelBlockHide();if(hoveredBlock===el)blockActions.classList.add('actions-visible')});
 slot.addEventListener('mouseleave',scheduleBlockHide);
 el.addEventListener('mouseenter',()=>showBlockActions(el));el.addEventListener('mouseleave',scheduleBlockHide);
 el.addEventListener('focus',()=>showBlockActions(el));el.addEventListener('blur',scheduleBlockHide);
 el.addEventListener('dblclick',e=>{if(e.target.closest('a'))return;cancelBlockHide();blockActions.classList.remove('actions-visible');blockActions.hidden=true;startBlockEdit(el)});
 el.addEventListener('keydown',e=>{if(!editing&&e.key==='Enter'){e.preventDefault();cancelBlockHide();blockActions.classList.remove('actions-visible');blockActions.hidden=true;startBlockEdit(el)}});
});
function beginStructure(draft){
 if(editing||busy||feedbackOpen)return false;
 structuralDraft=draft;editing=true;editNodes=[];blockActions.hidden=true;
 document.querySelector('.read-actions').hidden=true;document.querySelector('.edit-actions').hidden=false;
 document.getElementById('inline-reason').value='';document.body.classList.add('editing-report');
 editStatus().textContent=tr('尚未保存 · 可取消恢复','Unsaved · Cancel to restore');return true;
}
function insertBoundary(after,index){
 const gap=document.createElement('div');gap.className='block-insert-gap';
 const menu=document.createElement('details');const plus=document.createElement('summary');plus.textContent='＋';plus.setAttribute('aria-label',tr('新增内容块','Insert block'));menu.append(plus);
 const choices=document.createElement('div');choices.className='block-type-choices';
 for(const [kind,zh,en] of [['fact','事实','Fact'],['inference','推断','Inference'],['hypothesis','假设','Hypothesis'],['question','待验证问题','Question']]){
  const button=document.createElement('button');button.type='button';button.textContent=tr(zh,en);
  button.onclick=()=>{
   const node=document.createElement('article');node.className='inserted-block';
   const label=document.createElement('small');label.textContent=tr(zh+' · 人工新增，待核查',en+' · Human addition, unverified');
   const editor=document.createElement('div');editor.className='prose';editor.contentEditable='true';editor.setAttribute('role','textbox');editor.setAttribute('aria-label',tr('新增段落','New paragraph'));editor.dataset.placeholder=tr('在这里写内容…','Write here…');
   editor.onpaste=e=>{e.preventDefault();document.execCommand('insertText',false,e.clipboardData.getData('text/plain'))};
   node.append(label,editor);
   if(!beginStructure({action:'insert_block',index,kind,node,editor}))return;
   menu.open=false;gap.after(node);editor.focus();
  };choices.append(button);
 }
 menu.append(choices);gap.append(menu);after.after(gap);return gap;
}
const structureNodes=[...document.querySelectorAll('#report-reading .claim,#report-reading .report-body > [data-md-line],#report-reading .report-body > .report-table')];
if(!structureNodes.length&&state.selected&&state.selected.status!=='deleted'){
 const sentinel=document.createElement('span');(document.querySelector('#report-reading .report-body')||document.getElementById('report-reading')).append(sentinel);insertBoundary(sentinel,0);
}
if(structureNodes.length&&state.selected?.status!=='deleted'){
 const first=structureNodes[0],sentinel=document.createElement('span');first.before(sentinel);insertBoundary(sentinel,0);
 structureNodes.forEach(node=>{
  const claim=node.classList.contains('claim');
  const indices=claim?[Number(node.querySelector('[data-annotatable]').dataset.annotatable)-1]:node.hasAttribute('data-md-line')?[Number(node.dataset.mdLine)]:[...node.querySelectorAll('[data-md-line]')].map(el=>Number(el.dataset.mdLine));
  const start=Math.min(...indices),end=Math.max(...indices),count=claim?1:end-start+1;
  // Control is outside editable text; deleting a table operates on the whole table.
  let shell=node;
  if(!claim){shell=document.createElement('div');shell.className='structure-block';node.before(shell);shell.append(node);}
  shell.classList.add('structure-block');
  const remove=document.createElement('button');remove.type='button';remove.className='delete-block';remove.textContent=tr('删除','Delete');remove.setAttribute('aria-label',tr('删除这一块','Delete this block'));
  remove.onclick=()=>{if(!beginStructure({action:'delete_block',index:start,count,removed:shell}))return;shell.hidden=true;};shell.prepend(remove);
  const following=shell.nextElementSibling;const boundaryAnchor=following?.classList.contains('block-action-slot')?following:shell;
  insertBoundary(boundaryAnchor,end+1);
 });
}
const rejectButton=document.createElement('button'),editButton=document.createElement('button');
rejectButton.type=editButton.type='button';editButton.textContent=tr('编辑','Edit');blockActions.append(rejectButton,editButton);
editButton.onclick=()=>{if(!hoveredBlock||busy||editing)return;const target=hoveredBlock;blockActions.hidden=true;startBlockEdit(target)};
async function decideBlock(action){
 if(!hoveredBlock||busy||editing)return;
 const key=blockKey(hoveredBlock);busy=true;acceptButton.disabled=rejectButton.disabled=editButton.disabled=true;
 try{
  const response=await fetch('/api/research-archive',{method:'POST',headers:{'Content-Type':'application/json','X-Uteki-Request':'1'},body:JSON.stringify({snapshot_id:state.selected.id,action,expected_revision:state.selected.revision,block_id:key,block_hash:state.blocks[key]})});
  const result=await response.json();if(!response.ok)throw Error(result.error||response.status);
  state.selected.revision=result.revision;state.block_decisions=result.snapshot.block_decisions||{};updateProgress();updateDecisionButtons();
 }catch(error){const feedback=document.getElementById('feedback');feedback.hidden=false;feedback.textContent=tr('未保存：','Not saved: ')+error.message}
 finally{busy=false;acceptButton.disabled=rejectButton.disabled=editButton.disabled=false}
}
acceptButton.onclick=()=>decideBlock(accepted(blockKey(hoveredBlock))?'unaccept_block':'accept_block');
rejectButton.onclick=()=>decideBlock(rejected(blockKey(hoveredBlock))?'unaccept_block':'reject_block');


document.getElementById('language').addEventListener('click',updateProgress);
updateProgress();
document.getElementById('cancel-inline')?.addEventListener('click',()=>stopEditing(true));
document.getElementById('save-inline')?.addEventListener('click',async()=>{
 if(busy)return;
 if(structuralDraft){
  const draft=structuralDraft;
  const text=draft.editor?.textContent?.trim();
  if(draft.action==='insert_block'&&!text){editStatus().textContent=tr('请填写内容','Enter block text');return}
  await mutate(draft.action,{block_index:draft.index,block_count:draft.count||1,block_kind:draft.kind,text,human_notes:document.getElementById('inline-reason').value.trim()||tr('调整报告内容块','Change report blocks')});return;
 }
 const changed=editNodes.filter(x=>x.el.innerHTML!==x.html);
 if(!changed.length){stopEditing(false);return}
 const answer=structuredClone(state.selected.answer), lines=answer.report_markdown?.split('\\n');
 for(const {el} of changed){
  if(el.hasAttribute('data-md-line')){
   const i=Number(el.dataset.mdLine),value=inlineMarkdown(el);
   if(el.hasAttribute('data-md-cell')){
    if(value.includes('|')){editStatus().textContent=tr('表格内容不能包含竖线','Table text cannot contain a pipe');return}
    const cells=lines[i].trim().replace(/^\\||\\|$/g,'').split('|');cells[Number(el.dataset.mdCell)]=value;lines[i]='|'+cells.join('|')+'|';
   }else{const prefix=lines[i].match(/^\\s*(#{1,6}\\s+|-\\s+)/)?.[0]||'';lines[i]=prefix+value}
  }else answer.claims[Number(el.dataset.annotatable)-1].text=el.textContent;
 }
 if(lines)answer.report_markdown=lines.join('\\n');
 await mutate('edit',{answer,human_notes:document.getElementById('inline-reason').value.trim()||tr('正文原位修订','Inline report revision')});
});
window.addEventListener('beforeunload',e=>{if(editing&&(structuralDraft||editNodes.some(x=>x.el.innerHTML!==x.html))&&!busy){e.preventDefault();e.returnValue=''}});
document.addEventListener('click',e=>{if(editing&&e.target.closest('[contenteditable] a'))e.preventDefault()},true);
document.getElementById('opinion-form')?.addEventListener('submit',event=>{event.preventDefault();const data=new FormData(event.target);mutate('comment',{text:data.get('text'),kind:data.get('kind'),carry_forward:data.has('carry_forward')})});
const drawer=document.getElementById('source-drawer');
let sourceTrigger=null;
function closeSource(restoreFocus=false){drawer.hidden=true;if(restoreFocus)sourceTrigger?.focus()}
document.querySelectorAll('.citation-toggle').forEach(button=>button.onclick=()=>{
 const expanded=button.getAttribute('aria-expanded')==='true';
 document.getElementById(button.getAttribute('aria-controls')).hidden=expanded;
 button.setAttribute('aria-expanded',String(!expanded));
 button.querySelector('.more-label').hidden=!expanded;
 button.querySelector('.less-label').hidden=expanded;
});
document.querySelectorAll('[data-source]').forEach(link=>link.onclick=event=>{
 event.preventDefault();event.stopPropagation();sourceTrigger=link;drawer.hidden=false;
 const caption=document.getElementById('source-caption');caption.dataset.zh=link.dataset.sourceTitleZh||link.dataset.sourceTitle||'';caption.dataset.en=link.dataset.sourceTitle||'';caption.textContent=caption.dataset[lang()];
 const excerpt=document.getElementById('source-excerpt');excerpt.replaceChildren();
 if(lang()==='zh'&&link.dataset.quoteZh){const label=document.createElement('small');label.textContent='中文译文 · 辅助阅读';const translation=document.createElement('p');translation.textContent=link.dataset.quoteZh;excerpt.append(label,translation)}
 const label=document.createElement('small');label.textContent=tr('原文摘录','Original excerpt');const quote=document.createElement('blockquote');quote.textContent=link.title||link.dataset.fullQuote||tr('此引用未记录摘录。','No excerpt recorded for this reference.');excerpt.append(label,quote);
 document.getElementById('source-new-tab').href=link.dataset.source;document.getElementById('close-source').focus();
});
document.getElementById('close-source').onclick=()=>closeSource(true);
document.addEventListener('click',event=>{if(!drawer.hidden&&!drawer.contains(event.target))closeSource()});
document.addEventListener('keydown',event=>{if(event.key==='Escape')closeSource(true)});

'''

JS += '\n' + Path(__file__).with_name('annotations.js').read_text(encoding='utf-8')

CSS += """
.report-body {max-width:76ch;line-height:1.85;color:#243849}
.report-body h2,.report-body h3 {margin-top:1.8em;line-height:1.4}
.report-body p {margin:0.8em 0}.report-bullet {padding-left:1em}
.report-table {overflow-x:auto;margin:20px 0}.report-table table {border-collapse:collapse;width:100%;font-size:13px}
.report-table th,.report-table td {padding:10px;border-bottom:1px solid #dce5eb;text-align:left;vertical-align:top}
.report-table th {background:#f0f5f8}.history-jump {padding:8px 10px}
.revision-log {overflow-wrap:anywhere;border-top:1px solid #dce5eb;padding-top:18px}
.revision-log h2 {font-size:17px}.revision-log pre {white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;margin:6px 0}
.change-before,.change-after {padding:10px 12px;margin:8px 0;font-size:13px}
.change-before {background:#fff1ed;border-left:3px solid #b5674f}
.change-after {background:#edf5f3;border-left:3px solid #41816f}
.revision-lineage {padding-left:22px}.revision-lineage li {margin:12px 0}.revision-lineage small {display:block;color:#647583}
#edit-dialog {width:min(920px,94vw);max-height:90vh;overflow:auto;padding:26px}
#answer-editor textarea {width:100%;box-sizing:border-box;line-height:1.7;font:inherit}
#edit-dialog button:focus-visible,.history-jump:focus-visible {outline:2px solid #235c66;outline-offset:3px}
@media(max-width:600px){#edit-dialog{padding:14px}.report-table{max-width:86vw}}
"""
