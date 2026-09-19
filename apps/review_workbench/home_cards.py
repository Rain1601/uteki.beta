"""Real attention records in fixed cards, with in-card reading."""
from pathlib import Path
from hashlib import sha256
from apps.review_workbench.site_navigation import bi, e, page, report_groups


def render_home(universe, rows, now=None):
    from apps.review_workbench.attention_dashboard import attention_model, report_url
    model = attention_model(universe, rows, now)
    history = attention_model(universe, rows, now, history=True)
    companies = {c['id']: c for c in universe['companies']}
    states = {'candidate': ('待审核', 'Pending review'), 'draft': ('草稿', 'Draft'),
              'adopted': ('已采纳', 'Adopted'), 'rejected': ('已拒绝', 'Rejected'), 'archived': ('已归档', 'Archived')}

    def report_item(row, company, event=None):
        title = row.get('question') or row.get('title') or row.get('primary_title') or bi('研究报告', 'Research report')
        title_html = e(title) if row.get('question') or row.get('title') or row.get('primary_title') else title
        key = sha256((row['id'] + ':' + str(row.get('revision'))).encode()).hexdigest()[:24]
        answer = row.get('answer')
        if isinstance(answer, dict):
            text = answer.get('report_markdown') or answer.get('text')
            if not text:
                text = '\n\n'.join(str(c.get('text') or c.get('claim') or '') if isinstance(c, dict) else str(c) for c in answer.get('claims', []))
        else:
            text = str(answer or '')
        status = bi(*states.get(row.get('status'), ('待确认', 'Unconfirmed')))
        meta = bi(*event['kind']) + ' · ' + e(event['at'].strftime('%Y-%m-%d %H:%M')) if event else e(row.get('researcher_label') or row.get('researcher_id') or '')
        result = '<article class="hc-item" data-read-key="'+key+'"><button class="hc-open" aria-expanded="false"><span class="hc-meta">'+e(company['name'])+' · '+meta+'</span><strong>'+title_html+'</strong><span class="hc-state"><i aria-hidden="true"></i><span class="hc-unread">'+bi('未读','Unread')+'</span> · '+status+'</span><span class="hc-peek">'+e(str(text or '')[:180])+'</span></button>'
        result += '<template><div class="hc-reading"><p class="hc-meta">'+e(company['name'])+' · '+status+'</p><h3>'+title_html+'</h3><p class="hc-meta">'+bi('正文预览；完整引用和编辑见报告。','Text preview; open the report for full citations and editing.')+'</p><div class="hc-prose">'+(e(text) if text else bi('该报告暂无可预览的正文。','No preview text is available.'))+'</div></div><div class="hc-reading-actions"><button class="hc-back">'+bi('收起','Back')+'</button><button class="hc-unread-action">'+bi('标为未读','Mark unread')+'</button><a href="'+report_url(company,row)+'">'+bi('阅读与编辑报告','Read and edit report')+'</a></div></template></article>'
        return result

    def card(title, content, kind='', controls='', note=''):
        return '<section class="hc-card '+kind+'"><div class="hc-heading"><h2>'+bi(*title)+'</h2>'+controls+'</div><div class="hc-list" tabindex="0">'+content+'</div><div class="hc-detail" hidden></div><div class="hc-foot">'+note+'</div></section>'

    groups = []
    for item in model['focus'] + model['observe']:
        groups.extend((item['company'], latest) for _, latest, _ in item['groups'])
    groups.sort(key=lambda pair: pair[1].get('status') not in {'candidate','draft'})
    pending = sum(row.get('status') in {'candidate','draft'} for _,row in groups)
    body = '<div class="hc-intro"><div><p>'+e(model['day'])+' · '+bi('研究工作台','Research workspace')+'</p><h1>'+bi('今天关注什么','Where to focus today')+'</h1><p>'+bi(f'{len(groups)} 份研究报告，{pending} 份待审核；近 7 日有 {len(model["updates"])} 条研究变化。',f'{len(groups)} reports, {pending} pending review; {len(model["updates"])} research updates in 7 days.')+'</p></div><a href="/companies">'+bi('全部公司','All companies')+'</a></div><div class="hc-grid">'
    queue = ''.join(report_item(row, c) for c,row in groups) or '<p class="hc-empty">'+bi('暂无研究报告。进入公司查看原始材料。','No reports yet. Open a company to view source materials.')+'</p>'
    controls = '<label class="hc-filter"><input type="checkbox" id="hc-only-unread">'+bi('只看未读','Unread only')+'</label>'
    body += card(('今日要看','Reading queue'), queue, 'hc-primary', controls, bi('连续滑动 · 查看标记保存在本机，不代表已审核','Scroll to browse · Read marks are local, not approval'))
    recent = ''.join(report_item(v['report'],v['company'],v) for v in model['updates']) or '<p class="hc-empty">'+bi('近 7 日暂无研究变化。','No research updates in 7 days.')+'</p>'
    older = ''.join(report_item(v['report'],v['company'],v) for v in history['updates']) or '<p class="hc-empty">'+bi('暂无已记录的历史。','No recorded history.')+'</p>'
    body += card(('公司变化','Company updates'),'<div data-events="recent">'+recent+'</div><div data-events="history" hidden>'+older+'</div>',controls='<div class="hc-switch"><button data-history="recent" aria-pressed="true">'+bi('最近','Recent')+'</button><button data-history="history" aria-pressed="false">'+bi('历史','History')+'</button></div>',note=bi('研究记录变化，不代表行情或经营变化','Research changes, not market or operating changes'))
    additions = ''.join('<a class="hc-company" href="/companies/'+e(v['company']['id'])+'"><strong>'+e(v['company']['name'])+'</strong><span>'+e(v['at'].date().isoformat())+'</span></a>' for v in model['newcomers'])
    if not additions:
        additions = '<p class="hc-empty">'+bi('近 7 日暂无可确认的新增公司。','No confirmed additions in 7 days.')+'</p>'
    if model['missing_added']:
        additions += '<p class="hc-meta">'+bi(f'{model["missing_added"]} 家公司未记录加入时间。',f'Added dates are missing for {model["missing_added"]} companies.')+'</p>'
    additions += '<h3 class="hc-watch-title">'+bi('关注名单','Watchlist')+'</h3>' + ''.join('<a class="hc-company" href="/companies/'+e(c['id'])+'"><strong>'+e(c['name'])+'</strong><span>'+e(c.get('ticker'))+'</span></a>' for c in companies.values())
    body += card(('新增公司','New companies'),additions,note=bi('加入时间来自公司记录','Added dates come from company records'))
    for title, message in [(('最近新闻','Recent news'),('尚未接入新闻来源。后续在这里查看与公司关联的新闻。','News sources are not connected yet. Company news will appear here.')),(('持仓与投资组合','Holdings and portfolios'),('尚未接入持仓。后续查看各组合的持仓增减与权重变化。','Holdings are not connected yet. Portfolio position and weight changes will appear here.'))]:
        body += card(title,'<p class="hc-empty">'+bi(*message)+'</p>','hc-future',note=bi('待接入','Not connected'))
    body += '</div><p id="hc-status" role="status"></p>'
    body += '<style>'+Path(__file__).with_name('home_cards.css').read_text()+'</style><script>'+Path(__file__).with_name('home_cards.js').read_text()+'</script>'
    return page('注意力主页',body)
