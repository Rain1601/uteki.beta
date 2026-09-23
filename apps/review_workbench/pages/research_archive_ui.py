"""Company research snapshots: deliberately small, server-rendered review UI.

The UI is not an authority for adoption eligibility. The archive store must
repeat all status, version, and exclusivity checks on every POST.
"""
from apps.review_workbench.assets import asset_text
from datetime import datetime
from html import escape
import json
import hashlib
from pathlib import Path
import re
from urllib.parse import quote, urlencode, urlsplit
from zoneinfo import ZoneInfo
from apps.review_workbench.components.citation_translations import translated_quote
from apps.review_workbench.components.visual_system import workbench_page
from apps.review_workbench.components.report_text import render_report, report_outline


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
    from apps.review_workbench.components.archive_navigation import navigation, revision_history, editor_label
    from apps.review_workbench.components.site_navigation import company_tabs
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


CSS = asset_text('research_archive_ui.css')


JS = asset_text('research_archive_ui.js')

JS += '\n' + asset_text('annotations.js')

CSS += asset_text('research_archive_layout.css')
