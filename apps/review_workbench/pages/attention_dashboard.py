"""Attention is derived from recorded research, never inferred market movement."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from hashlib import sha256
from urllib.parse import quote
from apps.review_workbench.components.site_navigation import bi, e, page, report_groups

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


def render_dashboard(universe, rows, now=None):
    from apps.review_workbench.pages.home_cards import render_home
    return render_home(universe, rows, now)
