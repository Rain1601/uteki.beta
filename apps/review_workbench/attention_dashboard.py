"""Attention is derived from recorded research, never inferred market movement."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from hashlib import sha256
from urllib.parse import quote
from apps.review_workbench.site_navigation import bi, e, page, report_groups

ZONE = ZoneInfo('Asia/Shanghai')


def recorded_time(value):
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            if len(value) != 10:
                return None
            stamp = stamp.replace(tzinfo=ZONE)
        return stamp.astimezone(ZONE)
    except ValueError:
        return None


def attention_model(universe, rows, now=None, history=False):
    now = (now or datetime.now(ZONE)).astimezone(ZONE)
    cutoff = datetime.min.replace(tzinfo=ZONE) if history else now - timedelta(days=7)
    companies = universe['companies']
    by_company = {c['id']: [] for c in companies}
    for row in rows:
        if row.get('company_id') in by_company and row.get('status') != 'deleted':
            by_company[row['company_id']].append(row)
    focus, observe, updates, newcomers = [], [], [], []
    events_seen = set()
    actions = {'edit': ('人工修订', 'Human revision'), 'agent_edit': ('Agent 修订', 'Agent revision'),
               'adopt': ('报告已采纳', 'Report adopted'), 'review': ('报告已审核', 'Report reviewed'),
               'archive': ('报告已归档', 'Report archived'), 'reject': ('报告已拒绝', 'Report rejected')}
    for company in companies:
        research = by_company[company['id']]
        groups = report_groups(research)
        pending = [latest for _, latest, _ in groups if latest.get('status') in {'candidate', 'draft'}]
        for row in research:
            stamp = recorded_time(row.get('created_at') or row.get('run_started_at'))
            if stamp and cutoff <= stamp <= now:
                kind = ('新报告', 'New report') if not row.get('parent_snapshot_id') else ('报告修订', 'Report revision')
                updates.append(dict(company=company, report=row, at=stamp, kind=kind))
            for event in row.get('audit_events', []):
                identity = event.get('event_id')
                at = recorded_time(event.get('at'))
                action = event.get('action')
                # Revisions already appear through their immutable child snapshot.
                if not identity or identity in events_seen or action not in actions or action in {'edit', 'agent_edit'}:
                    continue
                events_seen.add(identity)
                if at and cutoff <= at <= now:
                    updates.append(dict(company=company, report=row, at=at, kind=actions[action]))
        current_updates = [u for u in updates if u['company']['id'] == company['id']]
        checkpoint = sha256(str(sorted((r['id'], r.get('revision'), r.get('status')) for r in research)).encode()).hexdigest()[:12]
        item = dict(company=company, pending=pending, groups=groups, updated=bool(current_updates), checkpoint=checkpoint)
        (focus if company.get('attention') == 'core' or pending or current_updates else observe).append(item)
        added = recorded_time(company.get('added_at'))
        if added and cutoff <= added <= now:
            newcomers.append(dict(company=company, at=added))
    focus.sort(key=lambda x: (not bool(x['pending']), not x['updated'], x['company'].get('attention') != 'core', x['company']['name']))
    observe.sort(key=lambda x: (x['company'].get('attention') != 'active', x['company']['name']))
    return dict(focus=focus, observe=observe, updates=sorted(updates,key=lambda x:x['at'],reverse=True),
                newcomers=sorted(newcomers,key=lambda x:x['at'],reverse=True),
                missing_added=sum(recorded_time(c.get('added_at')) is None for c in companies), day=now.date().isoformat())


def report_url(company, row):
    return '/companies/' + quote(company['id'], safe='') + '/reports/' + quote(row['id'], safe='')


def attention_row(item, day, checkable=True):
    company = item['company']
    url = '/companies/' + quote(company['id'],safe='')
    reason = bi('观察名单 · 关注', 'Watchlist · Active') if company.get('attention') == 'active' else bi('观察名单 · 对照', 'Watchlist · Context')
    if item['pending']:
        reason = bi(f"{len(item['pending'])} 份报告待审核", f"{len(item['pending'])} reports pending review")
    elif item['updated']:
        reason = bi('近 7 日有研究更新', 'Research updated in the last 7 days')
    elif company.get('attention') == 'core':
        reason = bi('重点关注 · 沿用观察名单', 'Core priority from the watchlist')
    row = '<article class="attention-row" data-attention-company="'+e(company['id'])+'"><div class="attention-company"><a href="'+url+'"><strong>'+e(company['name'])+'</strong></a><small>'+e(company['ticker'])+'</small></div><div class="attention-reason">'+reason
    if not item['groups']:
        row += '<small>'+bi('尚无研究报告', 'No research reports yet')+'</small>'
    row += '</div><div class="attention-actions">'
    target = item['pending'][0] if item['pending'] else (item['groups'][0][0] if item['groups'] else None)
    row += '<a href="'+(report_url(company,target) if target else url)+'">'+bi('查看报告' if target else '进入公司', 'Open report' if target else 'Open company')+'</a>'
    if checkable:
        key = day+':'+company['id']+':'+item['checkpoint']
        row += '<label><input type="checkbox" data-daily-check="'+e(key)+'">'+bi('今日已查看', 'Viewed today')+'</label>'
    return row+'</div></article>'


def render_legacy_dashboard(universe, rows, now=None):
    model = attention_model(universe, rows, now)
    body = '<div class="dashboard-heading"><div><p class="muted">'+e(model['day'])+' · '+bi('北京时间', 'Beijing time')+'</p><h1>'+bi('今天关注什么', 'Where to focus today')+'</h1><p>'+bi('从待审核报告和研究更新开始，再回到重点公司。', 'Start with pending reports and research updates, then return to priority companies.')+'</p></div><a href="/companies">'+bi('浏览全部公司', 'Browse all companies')+'</a></div>'
    body += '<div class="attention-layout"><section class="attention-queue"><div class="section-heading"><h2>'+bi('今日关注', 'Today’s focus')+'</h2><label class="quiet-control"><input type="checkbox" id="only-unread">'+bi('仅看未查看', 'Hide viewed')+'</label></div><p class="muted">'+bi('按待审核、研究更新和已有重点标记排列。查看标记仅保存在本机，不代表报告已审核。', 'Ordered by pending review, research updates and core priority. View marks stay in this browser and do not approve reports.')+'</p>'
    body += ''.join(attention_row(item,model['day']) for item in model['focus']) or '<p>'+bi('目前没有需要优先处理的公司。', 'No companies need priority attention.')+'</p>'
    body += '<p id="focus-complete" hidden>'+bi('今日关注列表已全部查看。可以继续浏览待观察公司。', 'All focus companies have been viewed. Continue with the watchlist.')+'</p>'
    body += '<details class="observe-list"><summary>'+bi(f"待观察公司（{len(model['observe'])}）", f"Watchlist ({len(model['observe'])})")+'</summary><p class="muted">'+bi('观察名单中未进入上方优先队列的公司；保留原有关注／对照分类。', 'Watchlist companies outside the priority queue; original Active / Context classifications are retained.')+'</p>'
    body += ''.join(attention_row(item,model['day'],False) for item in model['observe'])+'</details></section>'
    body += '<aside class="attention-updates"><h2>'+bi('发生了什么变化', 'What changed')+'</h2><p class="muted">'+bi('近 7 日研究记录；不代表行情或公司经营发生变化。', 'Research records from the last 7 days; not market or operating changes.')+'</p>'
    if model['updates']:
        body += '<div class="update-feed">'
        for event in model['updates'][:8]:
            body += '<article><time>'+e(event['at'].strftime('%m-%d %H:%M'))+'</time><p>'+bi(*event['kind'])+'</p><a href="'+report_url(event['company'],event['report'])+'">'+e(event['company']['name'])+'</a><small>'+e(event['report'].get('researcher_label') or event['report'].get('researcher_id'))+'</small></article>'
        body += '</div>'
        if len(model['updates']) > 8:
            body += '<p class="muted">'+bi(f"显示最近 8 条，共 {len(model['updates'])} 条；完整记录见公司报告。", f"Showing 8 of {len(model['updates'])} updates; full history is in company reports.")+'</p>'
    else:
        body += '<p>'+bi('近 7 日暂无已记录的研究更新。', 'No recorded research updates in the last 7 days.')+'</p>'
    body += '<h2>'+bi('新增公司', 'New companies')+'</h2>'
    for item in model['newcomers']:
        body += '<p><a href="/companies/'+e(item['company']['id'])+'">'+e(item['company']['name'])+'</a><small>'+e(item['at'].date().isoformat())+'</small></p>'
    if model['missing_added']:
        body += '<p class="muted">'+bi(f"{model['missing_added']} 家公司的加入时间未记录，暂不能判断是否为新增。", f"Added dates are missing for {model['missing_added']} companies; new additions cannot be determined for them.")+'</p>'
    elif not model['newcomers']:
        body += '<p>'+bi('近 7 日没有新增公司。', 'No new companies in the last 7 days.')+'</p>'
    body += '<p class="dashboard-source">'+bi('观察名单截至 ', 'Watchlist as of ')+e(universe.get('as_of'))+'</p></aside></div>'
    body += '<script>'+JS+'</script><style>'+CSS+'</style>'
    return page('注意力主页',body)


JS = '''document.addEventListener('DOMContentLoaded',()=>{
 const boxes=[...document.querySelectorAll('[data-daily-check]')],filter=document.getElementById('only-unread');
 function refresh(){let remaining=0;boxes.forEach(box=>{const row=box.closest('.attention-row');row.classList.toggle('viewed',box.checked);row.hidden=filter.checked&&box.checked;if(!box.checked)remaining++});document.getElementById('focus-complete').hidden=!(filter.checked&&boxes.length&&remaining===0)}
 boxes.forEach(box=>{try{box.checked=localStorage.getItem('uteki-viewed:'+box.dataset.dailyCheck)==='1'}catch{}box.addEventListener('change',()=>{try{localStorage.setItem('uteki-viewed:'+box.dataset.dailyCheck,box.checked?'1':'0')}catch{box.checked=false;alert('无法保存本机查看标记 / Cannot save view mark in this browser')}refresh()})});filter.addEventListener('change',refresh);refresh();
});'''
CSS = '''
.dashboard-heading{display:flex;justify-content:space-between;align-items:center;gap:28px;margin:4px 0 34px}.dashboard-heading h1{margin:2px 0 8px}.dashboard-heading p{margin:4px 0;max-width:65ch}.dashboard-heading>a{white-space:nowrap}.attention-layout{display:grid;grid-template-columns:minmax(0,1fr) 285px;gap:44px}.attention-queue>.section-heading{margin-top:0}.attention-queue>.section-heading h2,.attention-updates>h2:first-child{margin-top:0}.attention-queue>.muted,.attention-updates>.muted{font-size:13px;line-height:1.7}.quiet-control{font-size:12px;color:#596779;white-space:nowrap}.attention-row{display:grid;grid-template-columns:minmax(135px,1fr) minmax(170px,1.1fr) 96px;gap:18px;align-items:center;border-bottom:1px solid #e1e7ef;padding:19px 0}.attention-company a{color:#202b3b}.attention-company small,.attention-reason small{color:#596779;font-size:12px;margin-top:4px}.attention-reason{font-size:13px}.attention-actions{font-size:13px}.attention-actions label{display:flex;gap:3px;align-items:center;margin-top:8px;font-size:11px;color:#596779;white-space:nowrap}.attention-row.viewed .attention-company strong{font-weight:400;color:#596779}.attention-updates{border-left:1px solid #e1e7ef;padding-left:28px}.update-feed article{padding:13px 0;border-bottom:1px solid #e1e7ef}.update-feed time{font-size:12px;color:#596779}.update-feed p{font-size:13px;margin:4px 0}.update-feed small{font-size:12px;color:#596779;margin-top:3px}.observe-list{margin-top:30px}.observe-list summary{font-size:19px;font-weight:600;cursor:pointer;padding:12px 0}.observe-list>p{font-size:13px}.dashboard-source{font-size:12px;color:#596779;margin-top:30px}.attention-updates h2{font-size:18px}.attention-actions input,.quiet-control input{accent-color:#275dad}@media(max-width:1000px){.attention-layout{grid-template-columns:1fr}.attention-updates{border-left:0;padding-left:0;border-top:1px solid #e1e7ef;padding-top:24px}.update-feed{display:grid;grid-template-columns:repeat(2,1fr);gap:0 25px}}@media(max-width:580px){.dashboard-heading{display:block}.dashboard-heading>a{display:inline-block;margin-top:14px}.attention-row{grid-template-columns:minmax(0,1fr) 96px;gap:8px 15px}.attention-company{grid-column:1}.attention-reason{grid-column:1}.attention-actions{grid-column:2;grid-row:1/3}.update-feed{grid-template-columns:1fr}.quiet-control{font-size:11px}}
'''


def render_dashboard(universe, rows, now=None):
    from apps.review_workbench.home_cards import render_home
    return render_home(universe, rows, now)
