"""One open question, unchanged Single/Team engine and pinned material set."""
import asyncio
import os
from pathlib import Path
from uteki.agents import analysis_comparison as engine

ROOT = Path(__file__).resolve().parents[1]
QUESTION = '''Alphabet 未来 3～5 年最重要的增长驱动和下行风险是什么？
哪些业务变化可能导致公司价值上升或下降？对股价影响还需要哪些信息才能判断？
请自主选择和读取提供的材料，比较业务的重要性，给出有依据的优先级，而不只是罗列业务。
区分已披露事实、你的条件性推断和未知事项；在 claims 中明确标记事实或推断，引用对应证据。
请主动检查反向证据，说明验证这些判断需要追踪哪些变化。
材料不足时回答能够支持的部分并明确限制；没有估值或市场预期资料时不要猜测股价涨跌幅。
这不是历史盲测。仅使用提供的材料，不使用外部知识填补缺口。'''

if __name__ == '__main__':
    if not os.environ.get('AIHUBMIX_API_KEY'):
        raise SystemExit('AIHUBMIX_API_KEY is required in environment')
    engine.CASES = {'open_drivers_risks': QUESTION}
    asyncio.run(engine.run_comparison(
        ROOT, ROOT/'experiments/analysis_comparison/open-drivers-gpt54mini-v0.2',
        'gpt-5.4-mini', 'aihubmix', citation_mode='source_block'))
