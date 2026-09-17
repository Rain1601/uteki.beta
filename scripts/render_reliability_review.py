"""Compare every registered annual reliability run; never rank by preferred thesis."""
from decimal import Decimal
from html import escape
import json
from pathlib import Path
from render_annual_narrative import render
from uteki.agents.numeric_review import review_run

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'experiments/analysis_comparison'
RUNS = ['annual-narrative-single-v0.1','annual-narrative-single-v0.2-a','annual-narrative-single-v0.2-b',
        'annual-narrative-single-v0.3-a','annual-narrative-single-v0.3-b','annual-narrative-single-v0.4-a',
        'annual-narrative-single-v0.5-a']


def main():
    summary, rows = [], []
    for name in RUNS:
        folder = BASE/name
        path = folder/'run/result.json'
        if not path.exists():
            cost_path=folder/'run/costs.json'
            cost=json.loads(cost_path.read_text()) if cost_path.exists() else {}
            summary.append(dict(run=name,status='failed_or_incomplete',estimated_usd=cost.get('known_estimated_usd'),
                                cost_status='known_estimate' if cost else 'unavailable'))
            rows.append('<tr><td>'+escape(name)+'</td><td colspan="8">运行失败或未完成 / Incomplete</td></tr>')
            continue
        result = json.loads(path.read_text())
        costs = json.loads((folder/'run/costs.json').read_text())
        numeric = review_run(result['report'],folder/'run')
        (folder/'percentage-review.json').write_text(json.dumps(numeric,ensure_ascii=False,indent=2),encoding='utf-8')
        # Original v0.1 presentation remains frozen. New reading views are derived.
        if name != RUNS[0]:
            (folder/'review.html').write_text(render(folder,review=numeric), encoding='utf-8')
        calls = [json.loads(p.read_text()) for p in sorted((folder/'run').glob('tool-*.json'))]
        record = dict(run=name,status=result['status'],
            initial_errors=len(result.get('initial_validation_errors',result['validation_errors'])),
            final_errors=len(result['validation_errors']),repair_attempts=result.get('repair_attempts',0),
            model_calls=costs['requests'],tool_calls=result['tool_calls'],
            tool_errors=sum(isinstance(c['result'],dict) and bool(c['result'].get('error')) for c in calls),
            estimated_usd=costs['known_estimated_usd'],semantic_review='not_approved',
            percentage_coverage_errors=len(numeric['errors']))
        summary.append(record)
        status = '通过 · 仍待研究审核' if not record['final_errors'] else '未通过'
        values = [f'<a href="/experiments/{name}/review.html">{escape(name.replace("annual-narrative-single-",""))}</a>',
            str(record['initial_errors']),str(record['final_errors']),str(record['percentage_coverage_errors']),str(record['repair_attempts']),
            str(record['tool_errors']),str(record['model_calls']),f'${Decimal(record["estimated_usd"]):.4f}',status]
        rows.append('<tr>'+''.join('<td>'+v+'</td>' for v in values)+'</tr>')
    folder = BASE/'v1-reliability-review'
    folder.mkdir(exist_ok=True)
    total = sum((Decimal(s['estimated_usd']) for s in summary if s['run'] != RUNS[0] and s['estimated_usd'] is not None),Decimal(0))
    data = {'runs':summary,'new_estimated_usd':str(total),'actual_billed_usd':None,
            'scope':'P0-A progress only, not a 1.0 release or investment performance benchmark'}
    (folder/'summary.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Uteki 1.0 · 年度分析可靠性</title><style>
body{margin:0;background:#fff;color:#243347;font:17px/1.85 "Avenir Next","PingFang SC",sans-serif}main{max-width:1080px;margin:auto;padding:44px 24px}h1{font-size:32px;line-height:1.4}h2{font-size:23px;margin-top:46px}a{color:#285db0;text-underline-offset:4px}small,.muted{color:#68768a;font-size:14px}table{border-collapse:collapse;width:100%;font-size:15px}td,th{padding:12px 10px;text-align:left;border-bottom:1px solid #e0e6ef;white-space:nowrap}.scroll{overflow:auto}p{max-width:52em}li{margin:12px 0}a:focus-visible,summary:focus-visible{outline:3px solid #285db0;outline-offset:3px}details{margin-top:30px}summary{cursor:pointer;color:#285db0}@media(max-width:600px){h1{font-size:26px}main{padding:24px 18px}}</style><main>
<a href="/companies/alphabet?tab=research">Alphabet / 研究档案</a><h1>先确认结果可靠，再继续季度验证。</h1><p>这是 1.0 第一阶段的真实运行记录。失败版本也保留；检查通过只表示引用和章节结构合规，不代表数字、论证或投资判断已经通过审核。</p>
<div class="scroll"><table><thead><tr><th>版本 / Run</th><th>初稿检查错误</th><th>最终检查错误</th><th>百分比待核实</th><th>修订轮次</th><th>工具错误</th><th>模型调用</th><th>估算费用</th><th>自动检查</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table></div>
<p class="muted">新增测试累计估算 $'''+str(total)+''' / US$5 预算。v0.1 是此前基线费用，不计入本轮额度。按保存单价估算，未减缓存折扣，不是实际账单。单元测试和网页制作不产生模型费用。</p>
<h2>每次改变了什么</h2><ul><li>v0.1：原始独立报告。存在 8 处未读引用，没有修订阶段。</li><li>v0.2：加入最多一次补读修订和共享预算；两次同配置运行，一次仍失败、一次通过。没有隐藏不成功的样本。</li><li>v0.3：用五个命名章节避免重复和遗漏；仅压缩传输中的版式字段及空单元格，原文文本、数值、坐标与索引不变。两次运行均经历一次修订后通过引用检查。</li><li>v0.4：加入可追溯的表格计算工具；提示模型区分审计意见与业务质量、业务规模与风险重要性。结果以表格实测状态为准。</li></ul>
<h2>引用通过以后，仍要审核什么 / Open issues</h2><ul><li>v0.2-b 的收入同比写成 15.2%，原表计算应约 15.1%。说明引用有效并不等于算术正确。</li><li>v0.4-a 虽然调用了计算工具，但若干计算失败后仍写入 35.96% 的 Cloud 增速、31.98% 的公司营业利润率和 23.68% 的 Cloud 利润率。新增检查已能拦下这些无成功计算依据的数字；未修改原始输出。</li><li>“百分比待核实”是新增规则对历史结果的回放，不是原运行的检查结果。没有匹配记录并不必然代表算错；匹配也不等于业务口径正确，非百分比数字仍需人工核查。</li><li>v0.3-a 直接说“Other Bets 不重要”，缺少重要性的维度和风险分析；不应从小收入占比直接推出不重要。</li><li>无保留审计意见不能证明生意优质；经营利润、毛利率和边际利润也不能混用。</li><li>观察指标尚需落成可追踪的判断对象；缺少估值输入，不能宣称已能判断价格合适。</li></ul>
<p class="muted">v0.5 开始，百分比覆盖检查会直接参与一次性修订和最终失败判断；此前版本仅做事后回放。尚无记录的调用费用不计为零，累计值只统计已保存的已知估算。</p><p class="muted">以上为助手对具体样本的初步审核，不是独立审稿人评分，也不是全篇审核完成。请打开实际正文判断论证是否有用；不以 Cloud / Services 排名是否符合偏好评分。</p>
<h2>1.0 尚未完成的部分</h2><p>稳定假设与验证记录、正式季度修订链路、必要估值数据、页面发起任务与回档、完整效果验收仍待交付。这里不会自动采纳任何报告，也不覆盖之前的研究。</p><details><summary>机器可读记录 / Records</summary><a href="summary.json">完整对比数据</a></details></main></html>'''
    (folder/'review.html').write_text(page,encoding='utf-8')


if __name__ == '__main__':
    main()
