import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from apps.review_workbench.attention_dashboard import attention_model, render_dashboard, recorded_time
from apps.review_workbench.site_navigation import render_company_overview

NOW = datetime(2026,9,18,10,tzinfo=ZoneInfo('Asia/Shanghai'))


def company(identity, attention='active', **extra):
    return dict(id=identity,name=identity,ticker=identity.upper(),attention=attention,**extra)


def row(identity='r1', **extra):
    return dict(id=identity,company_id='alphabet',status='candidate',created_at='2026-09-16T06:00:00+00:00',revision=1,**extra)


class AttentionTests(unittest.TestCase):
    def setUp(self):
        self.universe = {'as_of':'2026-09-10','companies':[company('alphabet'),company('nvidia','core'),company('other')]}

    def test_priority_uses_reports_and_existing_attention_without_inventing_additions(self):
        model=attention_model(self.universe,[row()],NOW)
        self.assertEqual([x['company']['id'] for x in model['focus']],['alphabet','nvidia'])
        self.assertEqual(model['observe'][0]['company']['id'],'other')
        self.assertEqual(model['missing_added'],3)
        self.assertEqual(model['newcomers'],[])
        self.assertEqual(len(model['updates']),1)

    def test_future_and_old_updates_are_not_recent_and_dates_use_shanghai(self):
        rows=[row('old'),row('future'),row('deleted')]
        rows[0]['created_at']='2026-01-01T00:00:00+00:00'
        rows[1]['created_at']='2026-09-19T00:00:00+00:00'
        rows[2]['status']='deleted'
        self.assertEqual(attention_model(self.universe,rows,NOW)['updates'],[])
        self.assertEqual(recorded_time('2026-09-17T20:00:00+00:00').date().isoformat(),'2026-09-18')
        self.assertIsNone(recorded_time('bad'))
        self.assertIsNone(recorded_time('2026-09-18T01:00:00'))

    def test_revisions_do_not_double_count_pending_and_marks_change_with_revision(self):
        parent=row();child=row('r2',parent_snapshot_id='r1');child['created_at']='2026-09-17T00:00:00+00:00'
        model=attention_model(self.universe,[parent,child],NOW)
        item=model['focus'][0]
        self.assertEqual(len(item['pending']),1)
        before=item['checkpoint'];child['revision']=2
        self.assertNotEqual(before,attention_model(self.universe,[parent,child],NOW)['focus'][0]['checkpoint'])

    def test_added_dates_and_review_event_are_grounded(self):
        self.universe['companies'][0]['added_at']='2026-09-17'
        report=row();report['created_at']='2026-01-01T00:00:00+00:00'
        event={'event_id':'e1','action':'adopt','at':'2026-09-17T00:00:00+00:00'}
        report['audit_events']=[event,event];report['status']='adopted'
        model=attention_model(self.universe,[report],NOW)
        self.assertEqual(len(model['newcomers']),1)
        self.assertEqual(len(model['updates']),1)
        self.assertEqual(model['updates'][0]['kind'][0],'报告已采纳')

    def test_dashboard_links_and_company_detail_prioritize_reports(self):
        report=row(title='A report',question='What changed?')
        body=render_dashboard(self.universe,[report],NOW)
        self.assertIn('今天关注什么',body)
        self.assertIn('data-read-key=',body)
        self.assertIn('hc-grid',body)
        self.assertNotIn('role="dialog"',body)
        self.assertIn('/companies/alphabet/reports/r1',body)
        self.assertIn('不代表行情',body)
        detail=render_company_overview(self.universe['companies'][0],[report],{'documents':[]})
        self.assertLess(detail.index('class="featured-report"'),detail.index('class="research-support"'))
        self.assertIn('阅读与编辑报告',detail)

class HomeHistoryTests(unittest.TestCase):
    def test_history_includes_old_records_but_not_future_or_deleted(self):
        universe={'companies':[company('alphabet')]}
        old=row('old'); old['created_at']='2026-01-01T00:00:00+00:00'
        future=row('future'); future['created_at']='2027-01-01T00:00:00+00:00'
        deleted=row('deleted'); deleted['status']='deleted'
        model=attention_model(universe,[old,future,deleted],NOW,history=True)
        self.assertEqual([x['report']['id'] for x in model['updates']],['old'])

    def test_preview_escapes_content_and_keeps_status(self):
        universe={'companies':[company('alphabet')]}
        report=row(title='<script>unsafe</script>',answer={'text':'<img src=x onerror=alert(1)>'})
        body=render_dashboard(universe,[report],NOW)
        self.assertNotIn('<script>unsafe</script>',body)
        self.assertIn('&lt;img',body)
        self.assertIn('待审核',body)
        self.assertIn('尚未接入持仓',body)
