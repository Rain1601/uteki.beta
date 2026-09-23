"""Build an isolated interaction demo from verified, frozen research reports."""
import json
from pathlib import Path
from render_hypothesis_mvp import validate, source_link
from codex_hypothesis_mvp import OUT, ROOT, digest


def render():
    stages, _, _ = validate()
    seed={'reports':{},'hashes':{},'evidence':{}}
    for a in stages:
        stage=a['stage']
        seed['reports'][stage]={k:v for k,v in a.items() if not k.startswith('_')}
        seed['hashes'][stage]=a['_seal']['answer_sha256']
        label={'annual':'2025 10-K','q1':'2026 Q1','q2':'2026 Q2'}[stage]
        for e in a['_evidence']:
            seed['evidence'][e['id']]={**e,'url':source_link(a,e),'document':label}
    seed['identity']=digest(json.dumps(seed['hashes'],sort_keys=True).encode())[:16]+'-revision-demo-v1'
    assets=ROOT/'apps/review_workbench/static'
    css=(assets/'css/revision_demo.css').read_text()
    js=(assets/'js/revision_demo.js').read_text()
    page='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Alphabet · 年度研究修订 Demo</title><style>__CSS__</style></head><body class="rd">
    <header><div><a class="rd-brand" href="/companies/alphabet?tab=research">Uteki / Alphabet</a><small>年度主报告与验证报告 / Research & verification</small></div><div class="rd-links"><a href="review.html">原研究实验 / Research</a><button id="export">导出操作记录 / Export</button><button id="reset">重置演示 / Reset</button></div></header>
    <div class="rd-demo-note"><p><b>真实报告 · 隔离交互 Demo</b>　研究来自已完成的年报、Q1、Q2 实验；本页没有新调用模型。v1 的“生效”是演示设定，不是正式采纳。</p><p>请从 Q1 的一条建议开始：修订 → 保存候选 → 确认生效 → 查看 Q2 待复核。仅演示 Q1 到年度主报告的修订，Q2 保留原实验结果。</p><p id="storage"></p></div>
    <div id="notice" role="status" aria-live="polite"></div>
    <div class="rd-layout"><nav class="rd-nav" aria-label="报告与版本"><p>年度主报告 / Main report</p><div id="version-nav"></div><p>验证报告 / Verification</p><button data-view="q1"><b>2026 Q1</b><small>验证原假设，提出修订建议</small></button><button data-view="q2"><b>2026 Q2</b><small id="q2-status"></small></button><p>每份报告独立保留；修改依据可追溯。</p></nav><main class="rd-report" id="report"></main></div>
    <dialog id="editor" aria-labelledby="edit-title"><div class="rd-modal-head"><h2 id="edit-title"></h2><button data-close="editor">取消 / Cancel</button></div><p id="edit-basis" class="rd-muted"></p><div class="rd-pair"><div><h3>当前观点 / Current</h3><p id="edit-original"></p></div><div><h3>验证报告建议 / Suggestion</h3><p id="edit-suggestion"></p></div></div><label for="edit-text">修订后的观点 / Revised judgment</label><textarea id="edit-text"></textarea><label for="edit-watch">下一次验证事项 / Next test</label><textarea id="edit-watch"></textarea><label for="edit-reason">你为什么这样修改？/ Reason required</label><textarea id="edit-reason" placeholder="解释采纳、调整或保留意见的理由"></textarea><p class="rd-muted">保存只创建候选。模型不会替你确认；人工意见也不自动成为事实，后续分析仍需核对证据。</p><p id="edit-error" class="rd-error" role="alert"></p><button id="save-draft" class="rd-primary">保存候选修订 / Save candidate</button></dialog>
    <dialog id="adoption" aria-labelledby="adopt-title"><h2 id="adopt-title">确认修订生效 / Confirm adoption</h2><p id="adopt-info"></p><p id="adopt-error" class="rd-error" role="alert"></p><div class="rd-actions"><button data-close="adoption">返回检查 / Back</button><button id="adopt-final" class="rd-primary">确认生效（仅 Demo）/ Confirm</button></div></dialog>
    <dialog id="decision-dialog" aria-labelledby="decision-title"><div class="rd-modal-head"><h2 id="decision-title"></h2><button data-close="decision-dialog">取消 / Cancel</button></div><label for="decision-reason">处理理由 / Reason</label><textarea id="decision-reason"></textarea><p class="rd-muted">记录你的意见，不删除验证报告或反向证据。后续仍允许提出异议。</p><p id="decision-error" class="rd-error" role="alert"></p><button id="decision-save" class="rd-primary">保存意见 / Save</button></dialog>
    <dialog id="context-dialog" aria-labelledby="context-title"><div class="rd-modal-head"><h2 id="context-title">下次运行输入预览 / Context preview</h2><button data-close="context-dialog">关闭 / Close</button></div><p>这是拟用输入，不是已执行的运行。不把旧 Q2 结论当成新 Q2 的答案，也不使用未生效候选。当前 Demo 无模型重跑或自动事实审核。</p><pre id="context-content"></pre></dialog>
    <dialog id="source-dialog" aria-labelledby="source-title"><div class="rd-modal-head"><div><h2 id="source-title"></h2><a id="source-open" target="_blank" rel="noopener">打开原文 / Open original</a></div><button data-close="source-dialog">关闭 / Close</button></div><iframe id="source-frame" title="原始 SEC 材料 / SEC source"></iframe></dialog>
    <dialog id="reset-dialog" aria-labelledby="reset-title"><h2 id="reset-title">重置这份演示？ / Reset demo?</h2><p>只清除本页保存在浏览器中的演示修订和意见。可以先导出操作记录；正式档案和真实报告不会受影响。</p><div class="rd-actions"><button data-close="reset-dialog">取消 / Cancel</button><button id="reset-final">重置演示状态 / Reset</button></div></dialog>
    <script type="application/json" id="demo-data">__DATA__</script><script>__JS__</script></body></html>'''
    page=page.replace('__CSS__',css).replace('__DATA__',json.dumps(seed,ensure_ascii=False).replace('</','<\\/')).replace('__JS__',js)
    (OUT/'revision-demo.html').write_text(page)
    return seed


if __name__=='__main__':
    seed=render()
    print('Demo generated from frozen source hashes: '+json.dumps(seed['hashes']))
