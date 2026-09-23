"""Read-only material inventory. Discovery is not acquisition or extraction."""
from apps.review_workbench.assets import asset_text
from html import escape
from urllib.parse import quote
from apps.review_workbench.data.document_library import index_url
from apps.review_workbench.components.visual_system import workbench_page


def e(value):
    return escape(str(value), quote=True)


def bi(zh, en):
    return f'<span lang="zh">{e(zh)}</span><span lang="en">{e(en)}</span>'


@workbench_page('data')
def shell(title, body):
    return '''<!doctype html><html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>''' + e(title) + (''' · Uteki Data</title><style>''' + asset_text('company_data.css') + '''</style><header><a href="/companies">Uteki / Companies</a><a href="/companies/alphabet">Alphabet</a><a href="/data?company=alphabet">Data</a><button style="margin-left:auto" id="language">中文 / EN</button></header><main>''') + body + ('''</main><script>''' + asset_text('company_data.js') + '''</script></html>''')


def material_table(catalog):
    labels={'download_failed':('下载受阻','Download blocked'),'indexed_frozen':('已索引 · 已冻结','Indexed · Frozen'),'indexed_candidate':('已索引 · 待审核','Indexed · Candidate'),'downloaded':('已下载 · 未索引','Downloaded · Not indexed')}
    rows=[]
    for d in sorted(catalog.get('documents',[]), key=lambda d:(d['period_end'],d.get('published_at') or d['filed_at'],d['id']), reverse=True):
        # Document identity is explicit; unavailable sources retain a status page.
        label=labels.get(d['status'],('待获取','Pending'))
        kind = {'EARNINGS_CALL':('业绩电话会','Earnings call'),'EARNINGS_RELEASE':('业绩发布稿','Earnings release')}.get(d['form'],(d['form'],d['form']))
        rows.append(f'''<tr data-search="{e((d['title']+' '+d['accession']+' '+kind[0]).lower())}" data-year="{e(d['period_end'][:4])}" data-form="{e(d['form'])}"><td><a href="/documents/{quote(d['id'])}">{e(d['title'])}</a><small>{bi(*kind)}</small></td><td>{e(d['period_end'])}</td><td>{e(d.get('published_at') or d['filed_at'])}</td><td>{bi(*label)}</td><td><a href="{e(d['source_url'])}" target="_blank" rel="noopener">{bi('官方原文 ↗','Official source ↗')}</a></td></tr>''')
    rendered = ''.join(rows)
    for d in catalog.get('documents', []):
        if d['status'].startswith('indexed') and d.get('index_folder'):
            rendered = rendered.replace('/documents/' + quote(d['id']) + '"', e(index_url(d)) + '"')
    return '''<div class="controls"><input id="search" placeholder="搜索 / Search"><select id="year"><option value="">全部年度 / All years</option>''' + ''.join(f'<option>{y}</option>' for y in range(2026,2021,-1)) + '''</select><select id="form"><option value="">全部类型 / All forms</option><option>10-K</option><option>10-Q</option><option value="EARNINGS_CALL">电话会 / Earnings call</option><option value="EARNINGS_RELEASE">发布稿 / Earnings release</option></select></div><div class="scroll"><table><thead><tr>''' + ''.join(f'<th>{bi(*x)}</th>' for x in [('文档','Document'),('报告期末','Period end'),('公开日期','Published'),('处理状态','Status'),('原始来源','Source')]) + '</tr></thead><tbody>' + rendered + '</tbody></table></div>'


def render_company_data(company, catalog, data_view=False):
    body=f'<h1>{e(company["name"])} <span class="muted">/ {"Data" if data_view else e(company["ticker"])}</span></h1>'
    if company['id']!='alphabet':
        return shell(company['name'],body+'<p>'+bi('已纳入观察名单，尚未采集材料；不代表没有披露。','In the watchlist; materials not collected yet.')+'</p>')
    docs=catalog.get('documents',[])
    available=sum(d['status'].startswith('indexed') or d['status']=='downloaded' for d in docs)
    body+='<p class="muted">'+bi(f'2022–2026 · 已发现 {len(docs)} 份材料 · 本地可用 {available} 份',f'2022–2026 · {len(docs)} materials discovered · {available} available locally')+'</p>'
    body+='<nav><a href="#materials">'+bi('原始材料','Materials')+'</a><a href="/data?company=alphabet#structure">'+bi('结构化数据','Structured data')+'</a><a href="/data?company=alphabet#semantic">'+bi('业务语义结果','Business semantics')+'</a></nav>'
    if any(d['status']=='download_failed' for d in docs):
        body+='<p class="warning">'+bi('新增申报原文下载返回 HTTP 403。下列日期来自 SEC 申报记录，不表示原文已下载或已解析。','New original filings returned HTTP 403. SEC filing metadata below does not imply downloaded or parsed content.')+'</p>'
    body+='<h2 id="materials">01 / '+bi('原始材料','Source materials')+'</h2><p>'+bi('按报告期排序，公开日期单列。电话会日期为活动日期，文字稿上传时间未独立核验。2026 全年 10-K 尚未发布；第四季度不要求独立 10-Q。','Sorted by reporting period, with publication dates separate. Calls use event dates; transcript upload times are not independently verified. FY2026 10-K is not yet published; no standalone Q4 10-Q is expected.')+'</p>'+material_table(catalog)
    body+='<h2>'+bi('补充材料与缺口','Supplementary sources & gaps')+'</h2><p>'+bi('以下是待采集来源，不计入已下载文档。电话会需保留管理层发言与 Q&A；竞争对手材料须匹配业务和报告期，不能混入 Alphabet 自身披露。','These are acquisition targets, not downloaded documents. Calls should preserve prepared remarks and Q&A. Peer materials must be matched by business and reporting period, not attributed to Alphabet.')+'</p><table>'
    for zh,en,url in [
        ('财报发布稿 · 2022–2026 待补齐','Earnings releases · coverage pending','https://abc.xyz/investor/Earnings/default.aspx'),
        ('其他季度电话会 · 待补齐','Other quarterly calls · coverage pending','https://abc.xyz/investor/earnings/'),
        ('Microsoft · 云业务对照材料待采集','Microsoft · cloud peer sources pending','https://www.microsoft.com/en-us/Investor/'),
        ('Amazon · AWS 对照材料待采集','Amazon · AWS peer sources pending','https://ir.aboutamazon.com/'),
        ('Meta · 广告业务对照材料待采集','Meta · advertising peer sources pending','https://investor.atmeta.com/')]:
        body+=f'<tr><td>{bi(zh,en)}</td><td><a href="{e(url)}" target="_blank" rel="noopener">{bi("官方来源 ↗","Official source ↗")}</a></td></tr>'
    body+='</table>'
    if data_view:
        body+='<h2 id="structure">02 / '+bi('结构化数据','Structured data')+'</h2><p>'+bi('当前仅 FY2025 10-K：保真 Blocks、表格单元格、文档目录及来源定位。它们是材料的结构，不是业务结论。','Currently FY2025 10-K only: source blocks, table cells, document outline and source locations—not business conclusions.')+'</p><a href="/document-index">'+bi('打开已冻结的 Document Index →','Open frozen Document Index →')+'</a>'
        body+='<h2 id="semantic">03 / '+bi('Data Agent 业务语义结果','Data Agent semantic outputs')+'</h2><table><tr><td><a href="/result">'+bi('业务图 · 候选结果','Business map · candidate')+'</a></td><td>'+bi('业务节点、描述、披露口径与出处','Business nodes, descriptions, reporting categories and evidence')+'</td></tr><tr><td><a href="/result?view=cloud-spike&run=run-9856300a8d74fa77">'+bi('Google Cloud · 已审核快照','Google Cloud · reviewed snapshot')+'</a></td><td>'+bi('指定运行的事实与来源，不能代表其他年度已完成','Facts and evidence from this run, not coverage of other years')+'</td></tr></table><p class="muted">'+bi('Thesis / Factors 属于下游 Analysis Agent，不混入 Data Agent 的原始事实层。','Theses and factors belong to downstream Analysis Agent, not the raw factual layer.')+'</p>'
    body = body.replace('当前仅 FY2025 10-K：', '已下载文档均有独立候选索引；FY2025 10-K 为已冻结版本。结构层包括：')
    body = body.replace('Currently FY2025 10-K only:', 'Each acquired filing has its own candidate index; FY2025 10-K remains frozen. Structure includes:')
    if company['id'] == 'alphabet':
        body = '<nav style="display:flex;gap:30px;border-bottom:1px solid #d6dfd6;padding:12px 0"><a href="/companies/alphabet?tab=research">'+bi('研究档案','Research archive')+'</a><a href="/companies/alphabet?tab=data" aria-current="page">'+bi('公司数据','Company data')+'</a></nav>'+body
    return shell(company['name'],body)


def render_document_status(doc):
    return shell(doc['title'],f'<h1>{e(doc["title"])}</h1><p class="warning">'+bi('原文尚未取得，因此没有可展示的文档索引。','Original unavailable; no document index can be displayed.')+f'</p><p>{e(doc.get("error",doc["status"]))}</p><a href="{e(doc["source_url"])}" target="_blank" rel="noopener">'+bi('在 SEC 查看原文 ↗','View original at SEC ↗')+'</a><p><a href="/companies/alphabet">'+bi('返回材料列表','Back to materials')+'</a></p>')
