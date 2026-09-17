"""Presentation-only annual research narrative. Never edits frozen research."""
import re
from html import escape


def restyle_annual(page, annual, metrics, evidence):
    def refs(ids):
        links = []
        for key in ids:
            e = evidence[key]
            links.append(f'<a data-evidence="{key}" href="{escape(e["url"])}">{escape(e["label"])} <small>[2025 10-K]</small></a>')
        return '<div class="or-sources">依据：' + '； '.join(links[:3]) + (f'<details><summary>展开更多（{len(links)-3}）/ More</summary>{"； ".join(links[3:])}</details>' if len(links)>3 else '') + '</div>'

    def evidence_note(h):
        return f'<details class="or-detail"><summary>查看验证依据与边界 / Evidence & limits</summary><p>{escape(h["test"])}</p><p>{escape(h["falsifier"])}</p><p class="or-muted">{escape(h["unknown"])}</p></details>'

    h1, h2, h3 = annual['hypotheses']
    toc = [('annual','核心判断','Thesis'),('business','公司做什么','Business'),('industry','行业与竞争','Industry'),('earnings','赚钱与增长','Earnings'),('price','价格是否合适','Valuation'),('watch','接下来关注什么','To watch')]
    nav = '<aside class="or-rail"><p class="or-rail-title">这份报告 / Contents</p><nav aria-label="报告目录">'+''.join(f'<a href="#{key}">{zh}<small>{en}</small></a>' for key,zh,en in toc)+'</nav><p class="or-rail-foot">FY2025 10-K<br>材料截止 2026-02-05<br><span>初始研究 · 待审核</span></p></aside>'
    content = f'''
    <div class="or-layout">{nav}<main class="or-main">
      <header class="or-title"><p>Alphabet Inc. <span>2025 年报研究</span></p><h1>理解生意，再判断增长与价格。</h1><p class="or-subtitle">一份 10-K，形成初始判断。研究正文重新整理，原始结果与证据保持可追溯。</p></header>
      <section id="annual" class="or-thesis"><h2>我们目前的核心判断</h2>
        <p class="or-lead">Google Cloud 值得作为未来 3～5 年的重要增长来源继续研究：它正在扩大收入，也开始贡献更多利润。但 Alphabet 的投资价值，仍取决于搜索与广告能否保持盈利能力，以及增加的 AI 投入能否带来现金回报。</p>
        <p>这不是“Cloud 增长更快，所以公司一定更值钱”。2025 年 Services 的收入和利润增量仍大于 Cloud。我们看重的是 Cloud 的利润贡献能否持续增加，而不是用一个增速替代对整家公司的判断。<strong>目前可以形成经营假设，还不能得出当前股价便宜的结论。</strong></p>
        {refs(['A1','A2','A8'])}
      </section>
      <section id="business"><h2>公司做什么？<small>Business</small></h2>
        <p>可以先把 Alphabet 理解为：一部分业务帮助用户获取信息、消费内容，并让广告主付费触达这些用户；另一部分业务向企业提供云基础设施、平台和应用服务。此外，还有订阅、平台、设备及其他探索性业务。</p>
        <p>阅读财务数据时，先分清下面的关系。<strong>Search 不是与 Services 并列的分部，而是其中的一项收入类别。</strong></p>
        <div class="or-business-tree" aria-label="披露业务关系">
          <div><h3>Google Services</h3><p>广告，以及订阅、平台和设备收入。</p><ul><li>Google advertising<ul><li><b>Search &amp; other</b> · 搜索及其他广告收入</li><li>YouTube ads</li><li>Google Network</li></ul></li><li>Subscriptions, platforms &amp; devices<br><small>财务披露合并类别，不表示它们是一门相同的生意。</small></li></ul></div>
          <div><h3>Google Cloud</h3><p>企业云服务，以用量和订阅等方式收费。年报披露的增长主要来自 GCP 的基础设施和平台服务。</p><h3>Other Bets</h3><p>其他业务的合并披露类别；在这份初始报告中不把它作为主要增长判断的依据。</p></div>
        </div>{refs(['A1','A4'])}
      </section>
      <section id="industry"><h2>行业正在发生什么变化？<small>Industry & competition</small></h2>
        <p>只把它归为“互联网公司”太粗。就本报告关注的业务看，Alphabet 同时参与数字广告和企业云服务市场；两者都受到 AI 的影响，但影响利润的方式不同。</p>
        <p>对搜索和广告而言，关键在于：用户转向 AI 交互后，商业化能否跟上。对企业云而言，关键在于：新的使用需求能否形成持续收入，收入又能否覆盖服务与基础设施成本。公司在年报中同时提到 AI 搜索体验、企业 AI 方案、变现方式变化及竞争加剧。<strong>AI 是业务变化的方向，不是盈利改善的自动证明。</strong></p>
        <p>竞争风险也不只来自产品。搜索分发限制、数据共享等监管要求，可能影响原有的分发优势和竞争条件。这些是需要关注的风险，并非本报告已经确认的经营损失。</p>
        {refs(['A6','A7'])}
        <p class="or-caveat">行业判断的边界：当前材料主要是公司自身披露，尚不足以比较竞对份额、客户留存或整个行业的资本回报。因此暂不把“好行业”或“护城河稳固”写成已证实结论。</p>
      </section>
      <section id="earnings"><h2>靠什么赚钱，未来增长看哪里？<small>Earnings & growth</small></h2>
        <h3>现在的规模，仍主要在 Services</h3>
        <p>2025 年 Google Services 收入为 3,427.21 亿美元，Google Cloud 为 587.05 亿美元。Services 内部的 Search &amp; other 收入为 2,245.32 亿美元，同比增长约 13.35%。公司将搜索增长归因于查询增长、广告主支出和广告产品改进等共同因素，不能把它全部归因于 AI。</p>
        {refs(['A1','A5'])}
        <h3>未来的增量，重点看 Cloud 能否持续增加利润</h3>
        <p>Cloud 收入由 432.29 亿增至 587.05 亿美元，同比增长 35.80%；分部营业利润由 61.12 亿增至 139.10 亿美元，利润率由 14.14% 升至 23.69%。值得重视的不只是需求增加，而是收入增加的同时，分部盈利能力也在提高。</p>
        <p>如果企业用量和部署继续增加，且收入增长能够覆盖相应的基础设施与人员成本，Cloud 就可能持续扩大利润贡献。但这是对未来的推断。共享 AI 研发费用还有一部分计在集团层面，<strong>Cloud 分部利润并不等于 Alphabet 全部 AI 投资的回报。</strong></p>
        {refs(['A2','A3','A4'])}
        <h3>利润增长之外，还要看现金留下多少</h3>
        <p>2025 年经营现金流为 1,647.13 亿美元，购建固定资产支出为 914.47 亿美元。两者相减得到本报告的“简化自由现金流”：732.66 亿美元，2024 年为 727.64 亿美元。也就是说，利润改善尚未带来同等幅度的这一现金指标增长。</p>
        <p>这不代表投入已经失败，而是投资回收仍需要时间和证据。新增资本投入的回报、集团共享成本，以及未来的折旧负担，必须与业务增长一起看。</p>
        {refs(['A8','A9'])}
        <details id="annual-metrics" class="or-detail"><summary>展开年报关键数据 / Annual metrics</summary>__ANNUAL_MATRIX__<p class="or-muted">简化 FCF = 经营现金流 − 购建固定资产支出，不等于所有者收益，也未扣除收购支出及全部稀释影响。数字颜色只表示正负方向，不代表投资好坏。利润率为当期水平，其余为全年同比。</p></details>
      </section>
      <section id="price"><h2>现在的价格是否合适？<small>Valuation</small></h2>
        <p class="or-answer">目前不能判断。这是材料边界，不是看空结论。</p>
        <p>这份初始研究没有引入对应时点的股价、市场预期或未来现金流估值情景。即使 Cloud 增长和搜索盈利判断都成立，如果价格已经计入更乐观的结果，也不一定构成合适的投资。</p>
        <p>完成价格判断，需要在一个明确的估值日期，比较不同增长、利润率与资本开支假设下的每股价值，再检查当前价格留出了多大的误差空间。现阶段不提供目标价，也不以经营增长直接替代买入依据。</p>
      </section>
      <section id="watch"><h2>接下来，哪些变化最值得关注？<small>To watch</small></h2>
        <p>我们先集中跟踪三个判断，不把每一项财务波动都升级为新的投资观点。它们分别对应增长来源、主要业务的盈利能力和现金回报。</p>
        <article class="or-watch"><h3>Cloud 的增长能否继续转化为利润</h3><p>收入和利润率同时改善，会增加对利润增长的信心；若收入增长却伴随利润率持续下降，就需要重新考虑成本与竞争压力。遇到收购或披露口径变化，先拆分影响，不能直接认定有机增长更强。</p>{refs(['A2','A3','A4'])}{evidence_note(h1)}</article>
        <article class="or-watch"><h3>搜索的使用与变现是否受到侵蚀</h3><p>我们希望看到收入、查询或点击线索与商业化表现相互支持。若出现用户流失、变现下降或分发受损的直接证据，就应重新审视搜索盈利的可持续性。收入仍在增长，并不能单独证明护城河没有变弱。</p>{refs(['A5','A6','A7'])}{evidence_note(h2)}</article>
        <article class="or-watch"><h3>AI 投入之后，现金回报能否跟上</h3><p>经营现金的增加若持续赶不上资本开支，短期可分配现金就会承压。反过来，新增经营现金足以覆盖新增投入，会改善这一判断。需要区分短期建设支出与长期回报，不能仅凭一个季度就判断成功或失败。</p>{refs(['A8','A9'])}{evidence_note(h3)}</article>
        <p class="or-caveat">这是初始研究，不是已验证答案。此处不标注后续季度的支持或反驳，也不将任何观点涂成“已通过”。</p>
      </section>
      <footer class="or-footer"><details><summary>关于这份报告与原始结果 / Provenance</summary><p>本页是现有 Codex 年报研究的人工阅读整理版，并非新的 Agent 运行。只使用 FY2025 10-K 及其往年比较数据；未加入后续季度结果。原始研究不是历史盲测，证据定位正确也不等于推断正确。</p><p>Cloud 利润率按原始数值重新计算为 23.69%，原稿的 23.70% 取整误差保留在校正记录中。</p><p><a href="annual/answer.json">原始研究</a> · <a href="annual/materials.json">材料记录</a> · <a href="annual/evidence.json">出处记录</a> · <a href="review-notes.json">计算校正</a></p></details></footer>
    </main></div>'''
    matrix = '<div class="or-table"><table><thead><tr><th>指标</th><th>2025 10-K</th></tr></thead><tbody>'
    for label, key, eid in [('Google Services 收入同比','services_growth_pct','A1'),('↳ 其中：Search & other','search_growth_pct','A1'),('Google Cloud 收入同比','cloud_growth_pct','A1'),('Cloud 当期营业利润率','cloud_margin_pct','A2'),('简化 FCF 同比','fcf_growth_pct','A8')]:
        n = metrics[key][-1] if isinstance(metrics[key],list) else metrics[key]
        cls = 'hm-positive' if n>0 else 'hm-negative' if n<0 else 'hm-neutral'
        number = ('+' if n>0 and key.endswith('growth_pct') else '')+f'{n:.2f}%'
        matrix += f'<tr><th>{label}</th><td><a class="{cls}" data-evidence="{eid}" href="{escape(evidence[eid]["url"])}">{number}</a></td></tr>'
    matrix += '</tbody></table></div>'
    content = content.replace('__ANNUAL_MATRIX__',matrix)
    page = re.sub(r'<nav class="hm-nav".*?</nav><main class="hm-main">.*?</main>', lambda _:content, page, count=1, flags=re.S)
    page = page.replace('class="hm"','class="hm owner-report"',1)
    css = '''
    .hm.owner-report{background:#fff;color:#243347;font:17px/1.95 'Avenir Next','PingFang SC','Microsoft YaHei',sans-serif;margin:0;padding:0}
    .owner-report .hm-header{padding:18px 4vw;font-size:13px;border-bottom:1px solid #edf0f4}
    .owner-report .or-layout{max-width:1220px;margin:0 auto;display:grid;grid-template-columns:210px minmax(0,1fr);gap:60px;padding:0 36px}
    .owner-report .or-rail{position:sticky;top:22px;height:calc(100vh - 44px);align-self:start;padding-top:50px;overflow:auto}
    .owner-report .or-rail-title,.owner-report .or-rail-foot{font-size:12px;color:#68768a;line-height:1.8}
    .owner-report .or-rail nav a{display:block;padding:10px 13px;margin:4px 0;text-decoration:none;border-left:2px solid transparent;color:#536379;font-size:14px;line-height:1.5}
    .owner-report .or-rail nav a small{display:block;color:#788494;font-size:11px;margin-top:3px}
    .owner-report .or-rail nav a[aria-current="location"]{color:#285db0;border-color:#285db0;background:#f3f6fb;border-radius:0 6px 6px 0}
    .owner-report .or-rail nav a:hover{color:#285db0;background:#f7f9fc}.owner-report .or-rail-foot{margin:32px 13px}
    .owner-report .or-main{min-width:0;padding:54px 0 72px;max-width:850px}
    .owner-report .or-title>p:first-child{font-size:16px;font-weight:650;color:#243347;margin:0}.owner-report .or-title span{color:#68768a;font-weight:400;margin-left:16px;font-size:13px}
    .owner-report h1{font-size:clamp(28px,3vw,37px);line-height:1.45;letter-spacing:-.6px;margin:14px 0 18px;font-weight:650}
    .owner-report .or-subtitle{font-size:13px;color:#68768a;max-width:560px}
    .owner-report section{padding-top:56px;scroll-margin-top:22px}.owner-report h2{font-size:25px;font-weight:650;line-height:1.5;margin:0 0 20px}
    .owner-report h2 small{display:block;font-size:12px;font-weight:400;color:#7a8798;line-height:1.6;margin-top:5px}
    .owner-report h3{font-size:18px;font-weight:600;line-height:1.65;margin:28px 0 10px}.owner-report p{margin:16px 0;max-width:760px}
    .owner-report .or-thesis{padding-top:30px;margin-top:26px}.owner-report .or-thesis h2{font-size:14px;color:#285db0;margin:0 0 15px}
    .owner-report .or-lead{font-size:21px;line-height:1.85;font-weight:500;letter-spacing:.1px}.owner-report strong{font-weight:600}
    .owner-report .or-sources{font-size:12px;line-height:2.1;color:#758195;margin:15px 0 0}.owner-report .or-sources a{color:#3c669e;text-decoration-color:#c3d2e5}.owner-report .or-sources small{font-size:11px;background:#f4f6f9;padding:2px 4px;border-radius:3px;color:#64738a}
    .owner-report .or-business-tree{display:grid;grid-template-columns:1.15fr 1fr;gap:35px;margin:26px 0;padding:0 0 0 20px;border-left:2px solid #dce6f3}
    .owner-report .or-business-tree h3{margin:0 0 8px;font-size:17px}.owner-report .or-business-tree p,.owner-report .or-business-tree ul{font-size:14px;line-height:1.8;margin:8px 0 20px}.owner-report .or-business-tree ul{padding-left:20px}.owner-report .or-business-tree li{margin:5px 0}.owner-report .or-business-tree small{font-size:12px;color:#758195}
    .owner-report .or-caveat{font-size:14px;color:#596c82;border-left:2px solid #dce6f3;padding:8px 18px;margin-top:26px}
    .owner-report .or-detail{margin:22px 0;padding:14px 18px;background:#f7f9fc;border-radius:6px}.owner-report summary{font-size:13px;color:#526d91}.owner-report .or-detail p{font-size:14px;line-height:1.9}
    .owner-report .or-muted{color:#68768a;font-size:13px}.owner-report .or-answer{font-size:20px;font-weight:500}.owner-report .or-watch{padding:2px 0 16px}.owner-report .or-watch h3{margin-top:25px}
    .owner-report .or-table{overflow-x:auto}.owner-report .or-table table{font-size:14px}.owner-report .or-footer{margin-top:45px;padding-top:22px;border-top:1px solid #edf0f4;font-size:13px;color:#68768a}
    .owner-report a:focus-visible,.owner-report summary:focus-visible{outline:2px solid #285db0;outline-offset:5px}
    @media(max-width:850px){.owner-report .or-layout{display:block;padding:0 22px}.owner-report .or-rail{position:sticky;top:0;height:auto;padding:10px 0;background:#fffffff7;z-index:5}.owner-report .or-rail-title,.owner-report .or-rail-foot{display:none}.owner-report .or-rail nav{display:flex;overflow-x:auto;gap:8px}.owner-report .or-rail nav a{white-space:nowrap;font-size:12px;padding:7px 9px}.owner-report .or-rail nav a small{display:none}.owner-report .or-main{padding-top:28px}.owner-report .or-lead{font-size:19px}.owner-report section{scroll-margin-top:75px;padding-top:40px}.owner-report .or-business-tree{grid-template-columns:1fr;gap:10px}.owner-report .hm-header{padding:12px 22px}.owner-report .hm-header span{font-size:11px}.owner-report h2{font-size:23px}}
    @media(prefers-reduced-motion:no-preference){.owner-report .or-rail nav a{transition:background-color .15s,color .15s}}
    '''
    page = page.replace('</style>',css+'</style>',1)
    script = '''<script>const reportSections=[...document.querySelectorAll('.or-main section[id]')];const reportNav=[...document.querySelectorAll('.or-rail nav a')];function updateSection(){let active=reportSections[0];for(const section of reportSections){if(section.getBoundingClientRect().top<180)active=section;}reportNav.forEach(a=>{if(a.hash==='#'+active.id)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current');});}document.addEventListener('scroll',updateSection,{passive:true});updateSection();</script>'''
    return page.replace('</body>',script+'</body>')
