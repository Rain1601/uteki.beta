"""Pure projections: a researcher stream, one material row, explicit history."""
from html import escape
from urllib.parse import urlencode
import json
from uteki.agents.research_archive import Store
from apps.review_workbench.components.report_text import answer_text, text_changes, answer_changes


def navigation(snapshots, selected_id, researcher_id, scope, material_id, route, bi, badge, time, documents=None):
    documents = documents or {}
    rows = sorted(snapshots, key=Store._sort, reverse=True)
    selected = next((r for r in rows if r['id'] == selected_id), None)
    # Old snapshot links infer filters. Explicit mismatches do not show foreign content.
    researcher_id = researcher_id or (selected.get('researcher_id', 'unassigned') if selected else None) or next((r.get('researcher_id') for r in rows if r.get('researcher_id') == 'single-default'), None) or (rows[0].get('researcher_id', 'unassigned') if rows else 'single-default')
    researchers = {r.get('researcher_id', 'unassigned'): r.get('researcher_label') or r.get('researcher_id', '待归类 / Unassigned') for r in rows}
    stream = [r for r in rows if r.get('researcher_id', 'unassigned') == researcher_id]
    scope = scope or (selected.get('scope') if selected and selected in stream else None) or (stream[0]['scope'] if stream else 'company-drivers')
    filtered = [r for r in stream if r['scope'] == scope]
    mismatch = selected is not None and selected not in filtered
    if mismatch:
        selected = None
    groups = {}
    for row in filtered:
        groups.setdefault(row['primary_document_id'], []).append(row)
    def current(items):
        return next((r for r in items if r['status'] == 'adopted'), None)
    def preview(items):
        return current(items) or next((r for r in items if r['status'] == 'candidate'), None) or next((r for r in items if r['status'] != 'deleted'), items[0])
    def link(row):
        return route + '?' + urlencode(dict(tab='research', researcher=researcher_id, scope=scope, material=row['primary_document_id'], snapshot=row['id']))
    if selected is None and not mismatch:
        items = groups.get(material_id) if material_id else next(iter(groups.values()), None)
        if items:
            selected = preview(items)
    def select(name, label, options, value):
        return '<label>' + label + f'<select id="{name}">' + ''.join(f'<option value="{escape(k, quote=True)}"'+(' selected' if k == value else '')+f'>{escape(v)}</option>' for k,v in options.items()) + '</select></label>'
    agent_links = []
    for identity,label in researchers.items():
        own=[r for r in rows if r.get('researcher_id','unassigned') == identity]
        count=len({r['primary_document_id'] for r in own})
        target=route+'?'+urlencode({'tab':'research','researcher':identity})
        agent_links.append('<a class="agent-entry'+(' selected' if identity==researcher_id else '')+'" '+('aria-current="page" ' if identity==researcher_id else '')+'href="'+escape(target,quote=True)+'"><strong>'+escape(label)+'</strong><small>'+bi(f'{count} 份分析材料',f'{count} research materials')+'</small></a>')
    controls = '<div class="research-filters">' + select('scope-filter', bi('研究主题', 'Research scope'), {s['scope']: ('公司增长驱动与风险 / Company drivers' if s['scope']=='company-drivers' else s['scope']) for s in stream}, scope) + '</div>'
    timeline = []
    report_links = []
    for doc, items in groups.items():
        active, display = current(items), preview(items)
        count = sum(r['status'] == 'candidate' for r in items)
        is_selected = selected and selected['primary_document_id'] == doc
        form = documents.get(doc,{}).get('form') or display.get('primary_form')
        purpose = bi('年度研究','Annual research') if form=='10-K' else bi('验证假设','Hypothesis validation') if form else bi('类型待确认','Type unconfirmed')
        report_links.append('<a class="report-choice'+(' selected' if is_selected else '')+'" href="'+escape(link(display),quote=True)+'" '+('aria-current="page"' if is_selected else '')+'>'+escape(display.get('primary_title') or doc)+'</a>')
        versions_html = []
        for version in items:
            chosen = selected and selected['id'] == version['id']
            versions_html.append('<a class="snapshot version-row'+(' selected' if chosen else '')+'" data-status="'+escape(version['status'])+'" data-deleted="'+str(version['status']=='deleted').lower()+'" href="'+escape(link(version),quote=True)+'#analysis-report" '+('aria-current="page"' if chosen else '')+'><span>'+escape(time(version.get('created_at') or version.get('run_started_at')))+' · '+escape(version['id'][-8:])+'</span>'+badge(version['status'])+'<small>'+editor_label(version, bi)+'</small></a>')
        timeline.append('<div class="material-group"><a class="material-row" href="'+escape(link(display),quote=True)+'#analysis-report"><strong>'+escape(display.get('primary_title') or doc)+'</strong></a><small class="material-purpose">'+purpose+'</small><div class="material-versions">'+''.join(versions_html)+'</div></div>')
    versions = ''
    if selected:
        items = groups[selected['primary_document_id']]
        active = current(items)
        if active and selected['id'] != active['id']:
            versions += '<p class="notice">'+bi('正在查看非生效版本。', 'Viewing an inactive version. ')+'<a href="'+escape(link(active), quote=True)+'">'+bi('返回生效报告', 'Return to effective report')+'</a></p>'
        elif not active:
            versions += '<p class="notice">'+bi('此材料尚无生效报告；预览不代表采纳。', 'No effective report for this material. Preview is not adoption.')+'</p>'
    if mismatch:
        versions = '<p class="warning">'+bi('此版本不属于所选研究者或主题。请选择对应报告。', 'This snapshot does not belong to the selected researcher or scope.')+'</p>'
    material_list='<div class="material-list" aria-label="Analysis materials">'+''.join(timeline)+'</div>'
    return dict(rows=filtered, selected=selected, researcher_id=researcher_id, scope=scope, controls=controls,
                agents=''.join(agent_links),timeline=material_list,versions=versions, report_links=''.join(report_links), researcher_control=select('researcher-filter',bi('研究者','Researcher'),researchers,researcher_id))


def editor_label(snapshot, bi):
    if snapshot.get('edit_kind') == 'agent_revision':
        return bi('Agent 修订', 'Agent revision')
    if snapshot.get('edit_kind') == 'human_revision':
        return bi('人工修订', 'Human revision')
    return bi('原始报告', 'Original report')


def revision_history(snapshot, bi):
    result = '<section class="revision-log" id="revision-history"><h2>'+bi('修订历史', 'Revision history')+'</h2>'
    result += '<p>'+editor_label(snapshot, bi)+' · '+escape(snapshot.get('author') or '未记录 / Not recorded')+'</p>'
    result += '<p class="muted">'+bi('保存时间','Saved at')+' · '+escape(snapshot.get('edited_at') or snapshot.get('created_at') or '未记录 / Not recorded')+'</p>'
    if snapshot.get('edit_reason'):
        result += '<p>'+escape(snapshot['edit_reason'])+'</p>'
    provenance = snapshot.get('agent_provenance')
    if provenance:
        result += '<details><summary>'+bi('Agent 运行来源', 'Agent run provenance')+'</summary><dl>'
        for key, label in [('agent_id','Agent'),('model','Model'),('run_id','Run'),('artifact_path','Artifact'),('artifact_sha256','SHA256')]:
            result += '<dt>'+label+'</dt><dd>'+escape(str(provenance.get(key,'')))+'</dd>'
        result += '</dl></details>'
    changes = snapshot.get('edit_diff', {})
    if changes:
        result += '<details class="version-history" open><summary>'+bi('查看本次修改', 'View this revision’s changes')+'</summary>'
        for key, value in changes.items():
            if key == 'answer':
                result += answer_changes(value.get('before'), value.get('after'), bi)
                before, after = value.get('before'), value.get('after')
                if isinstance(before, dict) and isinstance(after, dict):
                    old = [c.get('citations') for c in before.get('claims', [])]
                    new = [c.get('citations') for c in after.get('claims', [])]
                    if old != new:
                        result += '<p>'+bi('引用也有变化，请重新核查来源。', 'Citations changed; verify the sources again.')+'</p>'
            else:
                result += '<h3>'+bi('修订说明' if key == 'human_notes' else key, key)+'</h3>'
                result += text_changes(str(value.get('before') or ''), str(value.get('after') or ''), bi)
        result += '</details>'
    block_events = snapshot.get('block_review_events', [])
    if block_events:
        result += '<details class="block-review-history"><summary>'+bi('逐块采纳记录','Block acceptance history')+'</summary><ul>'
        for event in block_events:
            result += '<li>'+bi('采纳' if event.get('accepted') else '撤销采纳','Accepted' if event.get('accepted') else 'Acceptance withdrawn')+' · '+escape(str(event.get('block_id','')))+' · '+escape(str(event.get('actor','')))+' · '+escape(str(event.get('at','')))+'</li>'
        result += '</ul></details>'
    lineage = snapshot.get('revision_lineage', [])
    if lineage:
        result += '<ol class="revision-lineage">'
        for item in lineage:
            target = '/companies/'+snapshot.get('company_id','alphabet')+'?'+urlencode({'tab':'research','snapshot':item['id']})
            stamp = item.get('edited_at') or item.get('created_at') or ''
            result += '<li><a href="'+escape(target,quote=True)+'">'+editor_label(item,bi)+'</a><small>'+escape(stamp)+' · '+escape(item.get('author') or '未记录 / Not recorded')+'</small></li>'
        result += '</ol>'
    events = snapshot.get('audit_events', [])
    if events:
        names = {'edit':('保存人工修订','Saved human revision'),'agent_edit':('保存 Agent 修订','Saved agent revision'),'seed':('导入原始报告','Imported original report'),'adopt':('采纳','Adopted'),'review':('人工审核','Human review')}
        result += '<details class="version-history"><summary>'+bi('操作记录', 'Decision history')+'</summary><ul>'
        for event in events:
            action = event.get('action','')
            result += '<li>'+bi(*names.get(action,(action,action)))+' · '+escape(' · '.join(str(event.get(k,'')) for k in ('at','actor','reason')))+'</li>'
        result += '</ul></details>'
    return result+'</section>'
