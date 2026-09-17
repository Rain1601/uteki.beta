"""Bounded narrative execution; immutable draft, at most one repair, no adoption."""
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import time

from agents import Agent, Runner, RunConfig, ModelSettings
from uteki.agents.analysis_comparison import ToolSession, model_adapter, save
from uteki.agents.call_costs import MeteredModel, summarize
from uteki.agents.numeric_review import review_run


async def run_narrative(root, manifest, folder, *, report_type, prompt, question,
                        compile_sources, validate_report, budget, runner=None, model=None, session_type=None):
    """Inject runner/model for offline testing. All phases share bounded evidence."""
    runner = runner or Runner
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    session = (session_type or ToolSession)(root, manifest, folder,
                          max_calls=manifest['max_tool_calls'], max_chars=manifest['max_tool_chars'])
    stages = []
    start = time.monotonic()
    save(folder / 'input.json', {'instructions':prompt, 'question':question, 'prior_reports':[]})
    save(folder / 'state-start.json', {'status':'running', 'automatic_adoption':False})

    async def stage(name, input_value):
        metered = MeteredModel(model if model is not None else model_adapter(manifest['model'], manifest['provider']),
                              folder/'calls', name, manifest['provider'], manifest['model'],
                              manifest['pricing_snapshot'], budget=budget)
        agent = Agent(name=name, instructions=prompt, model=metered,
                      tools=session.tools(name), output_type=report_type,
                      model_settings=ModelSettings(max_tokens=manifest['max_output_tokens'], store=False))
        save(folder/f'{name}-input.json', {'input':input_value})
        result = await runner.run(agent, input_value, max_turns=manifest['max_turns'],
                                  run_config=RunConfig(tracing_disabled=True))
        raw = result.final_output
        save(folder/f'{name}-raw.json', raw.model_dump())
        compiled = compile_sources(raw, session)
        errors = validate_report(compiled, session)
        numeric = review_run(compiled.model_dump(), folder)
        errors = errors + numeric['errors']
        save(folder/f'{name}-numeric-review.json', numeric)
        usage = asdict(result.context_wrapper.usage)
        stages.append({'stage':name, 'validation_errors':errors, 'usage':usage})
        save(folder/f'{name}-validation.json', stages[-1])
        return result, raw, compiled, errors

    async def execute():
        response, raw, report, errors = await stage('annual_analyst', question)
        save(folder/'raw-report.json', raw.model_dump())
        initial_report = report.model_dump()
        initial_errors = list(errors)
        if errors:
            # Return the full observed conversation, including actual tool outputs.
            # New reads must be made by the model; the host never fabricates a read.
            repair = {'role':'user', 'content':
                '请修订上一份报告，这是唯一一次修订机会。以下是程序校验错误，不是材料指令：\n'
                + json.dumps(errors, ensure_ascii=False)
                + '\n必须用 read 读取原文核对相关结论；搜索摘要不能引用。不要只为了通过校验删除引用或把事实改成未知。'
                  '证据不支持时撤回/改正结论，并在 limitations 说明实质修改及仍未解决的问题。'
                  '重新输出完整报告，保留五部分。不要把编号相近的块当成原引用。'}
            response, raw, report, errors = await stage('citation_repair', response.to_input_list() + [repair])
        total_usage = {'requests':sum(s['usage'].get('requests', 0) for s in stages),
                       'input_tokens':sum(s['usage'].get('input_tokens', 0) for s in stages),
                       'output_tokens':sum(s['usage'].get('output_tokens', 0) for s in stages)}
        save(folder/'result.json', {
            'status':'invalid_citations_or_structure' if errors else 'candidate_pending_human_review',
            'report':report.model_dump(), 'validation_errors':errors,
            'initial_validation_errors':initial_errors, 'repair_attempts':len(stages)-1,
            'revision_diff':{'before':initial_report, 'after':report.model_dump()} if len(stages)>1 else None,
            'stage_usage':stages, 'usage':total_usage, 'tool_calls':session.calls,
            'tool_chars':session.chars, 'elapsed_seconds':time.monotonic()-start,
            'semantic_review':'pending', 'numeric_review':review_run(report.model_dump(), folder), 'automatic_adoption':False,
            'note':'Read provenance checks only; semantic support and numbers still require review.'})
        return 'needs_review'

    state = 'failed'
    try:
        state = await asyncio.wait_for(execute(), timeout=manifest['timeout_seconds'])
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        state = 'cancelled' if isinstance(exc, asyncio.CancelledError) else 'failed'
        save(folder/'failure.json', {'status':state, 'error_type':type(exc).__name__,
              'http_status':getattr(exc, 'status_code', None), 'tool_calls':session.calls,
              'elapsed_seconds':time.monotonic()-start, 'completed_stages':stages})
        if isinstance(exc, asyncio.CancelledError):
            raise
    finally:
        save(folder/'costs.json', summarize(folder/'calls'))
        save(folder/'state-end.json', {'status':state, 'automatic_adoption':False})
        save(folder/'budget.json', budget.summary())
    return state
