"""Publish a transparent evidence replay of the assistant's owner-perspective QA."""
import gzip
import hashlib
import html as escape_html
import json
from pathlib import Path
from lxml import html
from uteki.agents.document_reader import DocumentReader

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'experiments/document_reader/owner-qa-v0.1'
SOURCE = ROOT / 'data/source_documents/alphabet_2025_10k'
URL = 'https://www.sec.gov/Archives/edgar/data/1652044/000165204426000018/goog-20251231.htm'
CASES = [
 ('巴菲特', '这门生意如何赚钱？', '主要商业机制可以回答；各业务的独立经济性尚未充分回答。',
  'Services 主要通过 Search、YouTube 和合作伙伴网络上的广告获得收入，另有订阅、平台和设备收入。广告需要承担流量获取、内容和基础设施成本。',
  '收入来源与成本项目支持商业机制描述；但 Services 是聚合分部，不能将其利润率直接赋予 Search 或 YouTube。',
  '独立业务的成本分配与单位经济性。', [(87,9),(456,9)]),
 ('巴菲特', '有多少现金真正属于股东？', '现金流差额可计算；正常化所有者收益不能确认。',
  'FY2025 经营现金流 164.7、资本开支 91.4，简单相减约 73.3（十亿美元）。这不是已完成调整的所有者收益。',
  '相减使用披露的四舍五入数字。税法变化影响当年现金流；维持性与增长性投入尚未可靠拆分，不能把单年差额直接外推。',
  '维持性资本需求、正常化现金流、股权激励与稀释分析。', [(502,4)]),
 ('巴菲特', '管理层是否善于配置资本？', '可以识别资本去向；质量仍待验证。',
  'FY2025 回购 454 亿美元、资本开支 914 亿美元，并披露拟收购 Wiz 和 Intersect。拟交易不等于已完成交易。',
  '配置行动不是回报证明：回购需要比较价格与价值，再投资需要检验新增收益，收购需要跟踪完成及兑现。',
  '回购估值、净股数变化、收购兑现、新增资本回报。', [(498,8)]),
 ('芒格', '什么可能破坏这门生意？', '可以提出风险假设；不能确定发生概率。',
  '2025 年超过 70% 的收入来自在线广告。入口、广告效果、合作关系、AI 与隐私变化都可能影响这一收入基础。',
  '待验证假设：用户入口或行为变化→广告价值与流量分配变化→收入或利润承压。这是分析假设，不是已证实的因果链，也不是穷尽风险。',
  '用户行为、广告主回报、竞争产品采用率及影响量化。', [(150,4),(110,3)]),
 ('芒格', '控制权与激励是否与小股东一致？', '控制权可确认；激励分析缺材料。',
  '披露两位创始人约拥有 52.7% 投票权。集中控制限制其他股东影响力，但不自动证明治理差。',
  '需要联合评价薪酬目标与实际行为。10-K 将薪酬、持股等信息引用至 Proxy Statement，不能用当前材料假装完成核查。',
  '2026 Proxy Statement、奖励目标、兑现记录。', [(300,2),(951,8)]),
 ('费雪', '产品与市场能支持长期增长吗？', '历史增长已回答；长期空间尚未验证。',
  '2024→2025：Cloud 收入 432.29→587.05 亿美元；Search & other 1,980.84→2,245.32 亿美元。',
  '两期数字证明历史增长，不能证明未来持续性；管理层列举的 Search 驱动包括查询量、广告支出与投放改进，不能全部归因为 AI。',
  '市场空间、份额、价格与用量拆分、留存和竞争验证。', [(510,6)]),
 ('费雪', '研发有效吗，还是仅仅花钱多？', '投入已回答；效率不能确认。',
  '研发支出 493.26→610.87 亿美元，占收入比例 14%→15%。',
  '研发费用衡量投入，不是成果；投入增加不能直接推导护城河增强，需要考虑产品商业化及时间差。',
  '研发成果、采用率、增量收益与失败项目成本。', [(546,3)]),
 ('费雪', '利润率改善能持续吗？', '历史分部盈利改善可验证；持续性待验证。',
  'Cloud 营业利润率：2024 年 61.12÷432.29≈14.1%；2025 年 139.10÷587.05≈23.7%。',
  '这是分部营业利润率，不是净利率或资本回报率。部分集中 AI 研发列入 Alphabet-level activities，不能假设已承担全部相关集团费用。',
  '完整成本归属、未来折旧、竞争与定价变化。', [(59,1),(510,2),(561,5)]),
 ('费雪', '管理层诚信、组织和销售能力优秀吗？', '当前材料不足，暂缓判断。',
  '本轮无法独立验证管理层诚信、组织关系、管理深度和销售能力。',
  '公司自述是线索而非独立验证；没有找到负面证据不等于证明优秀。需要比较历史承诺与实际兑现。',
  'Proxy Statement、客户与竞争者材料、长期承诺兑现记录。', [(951,8)]),
]

def main():
    OUT.mkdir(parents=True, exist_ok=False)
    reader = DocumentReader(SOURCE / 'indexes/v0.1')
    raw = gzip.decompress((SOURCE / 'source.html.gz').read_bytes())
    assert hashlib.sha256(raw).hexdigest() == reader.manifest['source_sha256']
    def save(name, value):
        (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    tree = html.fromstring(raw, parser=html.HTMLParser(encoding='utf-8'))
    paths = {tree.getroottree().getpath(el): el for el in tree.iter()}
    located = set()
    for block in reader.blocks:
        target = paths.get(block['dom_path'])
        if target is not None and target.getparent() is not None:
            target.addprevious(html.Element('span', id=block['block_id'], **{'class':'evidence-marker'}))
            located.add(block['block_id'])
    for el in tree.xpath('//*[@src]'):
        from urllib.parse import urljoin
        el.set('src', urljoin(URL, el.get('src')))
    for el in tree.xpath('//script'):
        el.drop_tree()
    style = html.Element('style')
    style.text = '.evidence-marker:target + *{outline:3px solid #cba52b;background:#fff2ba;scroll-margin-top:35px}'
    tree.append(style)
    (OUT/'source.html').write_bytes(html.tostring(tree, encoding='utf-8', include_meta_content_type=True))
    calls = [{'tool':'outline','arguments':{},'result':reader.outline()}]
    questions=[]
    for i,(lens,q,status,answer,rationale,gap,ranges) in enumerate(CASES,1):
        evidence={}
        refs=[]
        for ordinal,count in ranges:
            b=next(b for b in reader.blocks if b['ordinal']==ordinal)
            n=next(n for n in reader.index['nodes'] if n['kind']=='item' and reader.positions[n['start_block_id']]<=reader.positions[b['block_id']]<=reader.positions[n['end_block_id']])
            args={'node_id':n['node_id'],'start_block_id':b['block_id'],'count':count}
            result=reader.read(**args)
            calls.append({'case':f'q{i}','tool':'read','arguments':args,'result':result})
            refs.append(f'call-{len(calls):03}.json')
            for b in result['blocks']:
                assert b['block_id'] in located, b['block_id']
                evidence[b['block_id']]=b
        questions.append(dict(id=f'q{i}',lens=lens,question=q,status=status,answer=answer,rationale=rationale,gap=gap,calls=refs,evidence=list(evidence.values())))
    for i,c in enumerate(calls,1):save(f'call-{i:03}.json',c)
    save('answers.json',questions)
    save('manifest.json',{'mode':'Assistant-authored QA; actual evidence replay, not blind or autonomous evaluation', 'index_manifest':reader.manifest,'source_url':URL,'review_status':'pending','calls':len(calls),'external_model_calls':0,'external_model_api_cost':0,'cost_note':'No new external model API calls; Codex session usage not measured here.', 'limitations':['Questions and source ranges were known before replay.','Rationale is a review summary, not hidden chain of thought.','Single FY2025 filing, not exhaustive cross-document research.']})
    e=escape_html.escape
    sections=[]
    for q in questions:
        entries=[]
        for b in q['evidence']:
            label=f"p.{b['reported_page']} · #{b['ordinal']:04} · {b['type']}"
            entries.append(f'<details><summary><a href="source.html#{b["block_id"]}" target="source">{e(label)} ↗</a>　展开文本</summary><p class="quote">{e(b["text"])}</p><small>{e(b["block_id"])}</small></details>')
        sections.append(f'<section id="{q["id"]}"><small>{e(q["lens"])}视角 · 待审核</small><h2>{q["id"].upper()}　{e(q["question"])}</h2><p class="status">{e(q["status"])}</p><h3>回答</h3><p>{e(q["answer"])}</p><h3>分析说明 / Why</h3><p>{e(q["rationale"])}</p><h3>缺口与边界</h3><p>{e(q["gap"])}</p><details><summary>实际读取记录 · {len(q["calls"])} 次</summary><p>共享目录 → 已知证据范围读取；本次未记录新的自主搜索决策。</p>'+''.join(f'<a class="call" href="{f}" target="_blank">{f}</a>' for f in q['calls'])+'</details><h3>出处 · 点击页码在右侧定位</h3>'+''.join(entries)+'</section>')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Alphabet · 所有者视角 QA 审阅</title><style>
    *{box-sizing:border-box}body{margin:0;background:#fafbf9;color:#213b30;font:15px/1.65 system-ui}header{padding:16px 24px;border-bottom:1px solid #d4ddd6}h1{font-size:23px;margin:0}header p{margin:5px 0;font-size:13px;color:#617369}a{color:#146b4b}nav{display:flex;gap:17px;margin-top:8px}main{display:grid;grid-template-columns:minmax(440px,44%) 1fr;height:calc(100vh - 155px)}article{overflow:auto;padding:0 24px}section{padding:24px 0;border-bottom:1px solid #ccd7ce;scroll-margin-top:12px}h2{font-size:19px;margin:6px 0}h3{font-size:14px;margin:20px 0 5px}p{margin:7px 0}small{color:#64766b}.status{font-weight:600}.quote{white-space:pre-wrap;font:14px/1.6 Georgia,serif;color:#28332c}details{border-top:1px solid #dce4de;padding:8px 0}summary{cursor:pointer}iframe{width:100%;height:100%;border:0;border-left:1px solid #ccd7ce;background:white}.call{display:inline-block;margin-right:12px}@media(max-width:800px){main{grid-template-columns:1fr;height:auto}article{overflow:visible}iframe{height:65vh;position:sticky;bottom:0}header{height:auto}}
    </style><header><h1>Alphabet · 所有者视角 QA</h1><p>巴菲特 / 芒格 / 费雪思想改写的 9 问 · FY2025 10-K · v0.1 · 候选结果，非标准答案</p><p>助手分析 + 实际证据回放；非三个人物 Agent、非盲测。分析说明不是内部思维链。本次外部模型 API 调用 0 次。</p><nav>'''+''.join(f'<a href="#{q["id"]}">{q["id"].upper()}</a>' for q in questions)+'''<a href="manifest.json" target="_blank">版本</a><a href="call-001.json" target="_blank">目录记录</a></nav></header><main><article>'''+''.join(sections)+'''</article><iframe name="source" title="原文定位与高亮" src="source.html#block-000087-02c6e3d3"></iframe></main></html>'''
    (OUT/'review.html').write_text(page)
    print(json.dumps({'page':str(OUT/'review.html'),'questions':len(questions),'calls':len(calls),'all_evidence_located':True}))

if __name__=='__main__':main()
