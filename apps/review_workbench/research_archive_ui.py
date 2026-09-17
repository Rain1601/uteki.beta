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
    "candidate": ("未采纳", "Candidate"), "draft": ("未采纳", "Candidate"),
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
def render_archive(company, snapshots, selected_id=None, documents=None, researcher_id=None, scope=None, material_id=None):
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
            buttons.append('<button class="primary" data-action="adopt"' + ('' if can_adopt else ' disabled') + '>' + bi("采纳", "Adopt") + '</button>')
            if not can_adopt:
                buttons.append('<span class="muted action-hint">' + reason + '</span>')
            buttons.append('<button data-open="edit-dialog">' + bi("编辑报告", "Edit report") + '</button>')
        if status in {"candidate", "draft", "adopted"}:
            buttons.append('<button data-action="archive">' + bi("归档", "Archive") + '</button>')
        if status in {"candidate", "draft", "archived"}:
            buttons.append('<button data-action="delete">' + bi("删除", "Delete") + '</button>')
        if status == 'adopted' or status == 'rejected':
            buttons.append('<button data-open="edit-dialog">' + bi('编辑报告', 'Edit report') + '</button>')
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
        header = '<div class="detail-heading" id="analysis-report"><div><div class="eyebrow">' + scope_title + '</div><h1>' + heading + '</h1><div class="report-state">' + mode_label + _badge(status) + '</div></div></div>'
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
            comments.append('<article class="opinion"><div class="row"><small>' + e(comment.get("kind", "")) + ' · ' + e(_time(comment.get("created_at"))) + ' · ' + bi("已撤回" if withdrawn else "请求带入后续" if carrying else "仅本次意见", "Withdrawn" if withdrawn else "Carry-forward requested" if carrying else "This review only") + '</small>' + control + '</div>' + ('<blockquote class="opinion-quote">' + e(comment['source_selection']['quote']) + '</blockquote>' if comment.get('source_selection') else '') + '<div class="prose">' + e(comment.get("text", "")) + '</div><small>' + bi("系统审查", "System review") + ': ' + e(comment.get("review_status") or "not_reviewed") + '</small>' + ('<p>' + e(comment.get("review_reason", "")) + '</p>' if comment.get("review_reason") else '') + '</article>')
        comment_form = '' if status == "deleted" else '''<form id="opinion-form"><label for="opinion-text">''' + bi("写下你的意见", "Your review") + '''</label><textarea id="opinion-text" name="text" required rows="3" maxlength="12000"></textarea><div class="form-row"><label>''' + bi("意见类型", "Type") + ''' <select name="kind"><option value="preference">研究偏好 / Preference</option><option value="fact_claim">事实主张 / Factual claim</option><option value="hypothesis">投资假设 / Hypothesis</option></select></label><label><input type="checkbox" name="carry_forward"> ''' + bi("带入后续分析", "Carry into future analysis") + '''</label><button type="submit">''' + bi("保存意见", "Save review") + '''</button></div></form>'''
        opinions = '<section><h2>' + bi("人工意见与后续继承", "Human review & inheritance") + '</h2><p class="muted">' + bi("意见不是事实。类型由你指定，系统尚未复核时会明确标记；同版重跑可以使用未采纳报告上的意见；跨材料继承仍遵守采纳与时间规则，每次须重新审查。", "Opinions are not facts. Your selected type remains unreviewed until checked. Same-report reruns may use unadopted feedback; inheritance across materials requires adoption and time eligibility. Every run must review it.") + '</p>' + ''.join(comments) + comment_form + '</section>'
        links = []
        for key, zh, en in [("experiment_url", "原实验与费用", "Original experiment & cost"), ("source_url", "主材料原文", "Primary source")]:
            href = _url(s.get(key))
            if href:
                links.append(f'<a href="{href}" target="_blank" rel="noopener">' + bi(zh, en) + ' ↗</a>')
        trace = '<details class="run-details"><summary>' + bi("运行与审核记录", "Run & audit details") + '</summary><div class="links">' + ''.join(links) + '</div><dl class="metadata"><div><dt>Run ID</dt><dd>' + e(s.get("run_id", "—")) + '</dd></div><div><dt>Snapshot ID</dt><dd>' + e(s["id"]) + '</dd></div><div><dt>' + bi("证据校验", "Evidence validation") + '</dt><dd>' + e(s.get("validation_status", "unknown")) + '</dd></div></dl>' + _list(s.get("validation_errors") or s.get("citation_errors")) + '</details>'
        buttons.append('<a class="history-jump" href="#revision-history">'+bi('修订历史', 'Revision history')+'</a>')
        content = header + meta + notices + '<div class="actions">' + ''.join(buttons) + '</div>' + nav['versions'] + human_notes + '<section><h2>' + (bi('研究报告', 'Research report') if answer.get('report_markdown') else bi('当前判断', 'Current judgment')) + '</h2>' + _claims(answer, documents) + '</section><section><h2>' + bi("相对基线改变了什么", "What changed from the baseline") + '</h2>' + diff + '</section><section><h2>' + bi("未知项与材料限制", "Unknowns & limitations") + '</h2>' + _list(answer.get("limitations")) + '</section><section><h2>' + bi("核查发现与验证线索", "Findings & verification leads") + '</h2>' + _list(answer.get("findings")) + '</section>' + opinions + trace
        if answer.get('report_markdown'):
            content = header + meta + notices + '<div class="actions">' + ''.join(buttons) + '</div>' + nav['versions'] + human_notes + _claims(answer, documents) + opinions + trace
        client["selected"] = {"id": s["id"], "revision": s.get("revision", 1), "primary_inferred": s.get("primary_inferred", False), "competitors": [r.get("label") or r["id"] for r in candidates], "human_notes": s.get("human_notes", "")}
        if question:
            content += '<details class="run-details"><summary>' + bi('完整研究问题与要求', 'Full research query') + '</summary><div class="prose">' + e(question) + '</div></details>'
        client['selected']['status'] = status
        client['selected'].update(answer=answer, material_id=s['primary_document_id'], slot_revision=s.get('slot_revision'),
                                  effective={'id': effective['id'], 'revision': effective['revision']} if effective else None)
    else:
        content = nav['versions'] + content
    payload = json.dumps(client, ensure_ascii=False).replace('<', '\\u003c')
    drawer = '<div id="source-drawer" hidden><div class="source-toolbar"><strong>' + bi("原文证据", "Source evidence") + '</strong><a id="source-new-tab" target="_blank" rel="noopener">' + bi("新窗口 ↗", "New tab ↗") + '</a><button id="close-source" aria-label="Close source">×</button></div><div id="source-caption"></div><iframe id="source-frame" title="Original evidence" sandbox="allow-same-origin allow-scripts"></iframe></div>'
    return '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>''' + e(company_name) + ''' · Research Archive</title><style>''' + CSS + '''</style></head><body><header><a href="/companies">Uteki / ''' + bi("公司", "Companies") + '''</a><strong>''' + e(company_name) + '''</strong><button id="language">中文 / EN</button></header>''' + company_tabs(company_id, 'reports') + '''<div id="feedback" role="status" hidden></div><main><aside><div class="sidebar-heading"><strong>''' + bi("研究者", "Researchers") + '''</strong></div><p class="muted compact">''' + bi("独立研究，独立版本与上下文。", "Separate research streams and context.") + '''</p>''' + ''.join(timeline) + '''</aside><div class="detail">''' + content + '''</div><div class="material-rail" role="complementary" aria-label="Report navigation">''' + report_outline(selected.get('answer') if selected else None, bi) + '''<div class="material-toolbar"><h2>''' + bi("报告版本", "Report versions") + '''</h2>''' + nav['controls'] + '''<label class="version-filter">''' + bi("版本状态", "Version status") + '''<select id="version-status"><option value="all" data-zh="全部版本" data-en="All versions">全部版本</option><option value="adopted" data-zh="已采纳" data-en="Adopted">已采纳</option><option value="candidate" data-zh="待审核" data-en="Pending">待审核</option><option value="archived" data-zh="已归档" data-en="Archived">已归档</option><option value="rejected" data-zh="已拒绝" data-en="Rejected">已拒绝</option></select></label><label class="deleted-filter"><input type="checkbox" id="show-deleted"> ''' + bi("显示已删除历史", "Show deleted history") + '''</label></div><p class="material-help">''' + bi("按主材料公开时间排序；每份材料保留一个生效报告，历史版本按需展开。", "By primary-source publication. One effective report per material; revisions remain available.") + '''</p>''' + nav['timeline'] + (revision_history(nav['selected'], bi) if nav['selected'] else '') + '''<details class="context-policy"><summary>''' + bi("后续分析的上下文规则", "Context policy for future analyses") + '''</summary><p>''' + bi("10-K：继承去年、前年的已采纳 10-K 分析。10-Q、电话会和竞对材料：以最近可用的已采纳公司 10-K 分析为基线，验证假设是否得到支持、被削弱、被否定或证据仍不足。", "10-K: inherit adopted annual analyses from the prior two fiscal years. 10-Q, calls and competitor materials: test hypotheses against the latest eligible company 10-K analysis.") + '''</p><p>''' + bi("仅限同一 Agent 与研究主题，遵守材料时间边界。缺失基线明确记录；历史运行不改写。重跑入口会冻结并传入修改意见；保存意见不会自动运行模型。", "Same researcher and scope, with time-bound eligibility. Missing baselines are explicit. Historical runs are unchanged. The rerun entry point freezes and passes feedback; saving does not run a model.") + '''</p></details></div></main>''' + drawer + '''<dialog id="edit-dialog"><form id="edit-form"><h2>''' + bi("编辑报告", "Edit report") + '''</h2><p>''' + bi("保留模型原始答案，新建带人工说明的修订。引用校验失败不会因编辑自动变成通过。", "The original answer is retained. This creates a revision with human notes, not a new model run. Editing does not bypass evidence checks.") + '''</p><label for="human-notes">''' + bi("人工修订说明", "Human notes") + '''</label><textarea id="human-notes" name="human_notes" required rows="3" maxlength="20000"></textarea><div class="actions"><button type="button" id="cancel-edit">''' + bi("取消", "Cancel") + '''</button><button type="submit" class="primary">''' + bi("保存为新版本", "Save new version") + '''</button></div></form></dialog><script type="application/json" id="archive-state">''' + payload + '''</script><script>''' + JS + '''</script></body></html>'''


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
document.getElementById('language').onclick=()=>{const l=lang()==='en'?'zh':'en';document.documentElement.dataset.language=l;localStorage.setItem('data-language',l);hideCitationPreview();const caption=document.getElementById('source-caption');caption.textContent=caption.dataset[l]||''};
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
const dialog=document.getElementById('edit-dialog');
document.querySelectorAll('[data-open]').forEach(b=>b.onclick=()=>{
 document.getElementById('human-notes').value='';
 document.getElementById('answer-editor')?.remove();
 const fields=document.createElement('div');fields.id='answer-editor';
 const intro=dialog.querySelector('p');intro.textContent=tr('修改正文并说明原因。保存为新修订，原报告和引用保持不变；新修订需重新审核。','Edit text and explain why. Save a new revision; the original and citations stay intact. Review is required.');
 function field(label,value,key){const l=document.createElement('label');l.textContent=label;const t=document.createElement('textarea');t.rows=4;t.maxLength=20000;t.value=value;t.dataset.editKey=key;l.append(t);fields.append(l);}
 if(typeof state.selected.answer.report_markdown==='string'){field(tr('报告正文（支持 Markdown）','Report text (Markdown)'),state.selected.answer.report_markdown,'report_markdown');const area=fields.querySelector('textarea');area.rows=22;area.maxLength=60000;}
 (state.selected.answer.claims||[]).forEach((c,i)=>field(tr('判断 ','Claim ')+(i+1),c.text,'claim-'+i));
 ['limitations','findings'].forEach(k=>{if(Array.isArray(state.selected.answer[k]))field(k==='limitations'?tr('未知项（每行一项）','Limitations (one per line)'):tr('验证线索（每行一项）','Findings (one per line)'),state.selected.answer[k].join('\\n'),k)});
 intro.after(fields);dialog.showModal();
});
document.getElementById('cancel-edit').onclick=()=>dialog.close();
document.getElementById('edit-form').onsubmit=event=>{event.preventDefault();const answer=structuredClone(state.selected.answer);document.querySelectorAll('[data-edit-key]').forEach(t=>{const k=t.dataset.editKey;if(k==='report_markdown')answer[k]=t.value;else if(k.startsWith('claim-'))answer.claims[Number(k.slice(6))].text=t.value;else answer[k]=t.value.split('\\n').filter(v=>v.trim())});mutate('edit',{answer,human_notes:new FormData(event.target).get('human_notes')})};
document.getElementById('opinion-form')?.addEventListener('submit',event=>{event.preventDefault();const data=new FormData(event.target);mutate('comment',{text:data.get('text'),kind:data.get('kind'),carry_forward:data.has('carry_forward')})});
const drawer=document.getElementById('source-drawer');
const citationPreview=document.createElement('div');
citationPreview.id='citation-preview';citationPreview.role='tooltip';citationPreview.hidden=true;document.body.append(citationPreview);
let previewLink=null,previewTimer;
function hideCitationPreview(){clearTimeout(previewTimer);citationPreview.hidden=true;previewLink?.removeAttribute('aria-describedby');previewLink=null}
function showCitationPreview(link){
 clearTimeout(previewTimer);previewLink?.removeAttribute('aria-describedby');previewLink=link;
 citationPreview.textContent=lang()==='zh'?(link.dataset.quoteZh?'中文译文（辅助阅读，待人工复核）\\n'+link.dataset.quoteZh+'\\n\\n英文引用\\n'+link.dataset.fullQuote:'暂无中文译文 · 以下为英文引用\\n'+link.dataset.fullQuote):link.dataset.fullQuote;
 citationPreview.hidden=false;citationPreview.scrollTop=0;link.setAttribute('aria-describedby',citationPreview.id);
 const rect=link.getBoundingClientRect(),width=citationPreview.offsetWidth,height=citationPreview.offsetHeight;
 citationPreview.style.left=Math.max(12,Math.min(rect.left,innerWidth-width-12))+'px';
 citationPreview.style.top=Math.max(12,rect.bottom+8+height<=innerHeight-12?rect.bottom+8:rect.top-height-8)+'px';
}
const deferHidePreview=()=>{previewTimer=setTimeout(hideCitationPreview,180)};
document.querySelectorAll('.evidence-text').forEach(link=>{
 link.dataset.fullQuote=link.title;link.removeAttribute('title');
 link.addEventListener('mouseenter',()=>showCitationPreview(link));link.addEventListener('mouseleave',deferHidePreview);
 link.addEventListener('focus',()=>showCitationPreview(link));link.addEventListener('blur',deferHidePreview);
 link.addEventListener('click',hideCitationPreview);
});
citationPreview.addEventListener('mouseenter',()=>clearTimeout(previewTimer));citationPreview.addEventListener('mouseleave',deferHidePreview);
document.addEventListener('scroll',event=>{if(event.target!==citationPreview)hideCitationPreview()},true);
window.addEventListener('resize',hideCitationPreview);
document.addEventListener('keydown',event=>{if(event.key==='Escape')hideCitationPreview()});
document.querySelectorAll('.citation-toggle').forEach(button=>button.onclick=()=>{
 const expanded=button.getAttribute('aria-expanded')==='true';
 document.getElementById(button.getAttribute('aria-controls')).hidden=expanded;
 button.setAttribute('aria-expanded',String(!expanded));
 button.querySelector('.more-label').hidden=!expanded;
 button.querySelector('.less-label').hidden=expanded;
});
document.querySelectorAll('[data-source]').forEach(link=>link.onclick=event=>{event.preventDefault();event.stopPropagation();drawer.hidden=false;document.body.classList.add('source-open');const caption=document.getElementById('source-caption');caption.dataset.zh=link.dataset.sourceTitleZh;caption.dataset.en=link.dataset.sourceTitle;caption.textContent=caption.dataset[lang()];document.getElementById('source-frame').src=link.dataset.source;document.getElementById('source-new-tab').href=link.dataset.source;document.getElementById('close-source').focus()});
function closeSource(){drawer.hidden=true;document.body.classList.remove('source-open')}
document.getElementById('close-source').onclick=closeSource;
document.addEventListener('keydown',event=>{if(event.key==='Escape')closeSource()});
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
