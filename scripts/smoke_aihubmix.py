"""Small real SDK tool+schema compatibility probe. Never prints credential or API exception."""
import asyncio
from dataclasses import asdict
import json
import traceback
from agents import Agent,Runner,RunConfig,ModelSettings,function_tool
from pydantic import BaseModel
from uteki.agents.runtime.model_factory import model_adapter

called=[]
@function_tool
def probe() -> str:
    """Return the verification code required for this test."""
    called.append(True)
    return 'uteki-probe-2026'

class Result(BaseModel):
    code:str

async def main():
    try:
        agent=Agent(name='compatibility',model=model_adapter('gpt-5.4-mini','aihubmix'),
            instructions='Call probe then return its code in the structured result.',tools=[probe],output_type=Result,
            model_settings=ModelSettings(max_tokens=1000,store=False))
        result=await asyncio.wait_for(Runner.run(agent,'Check tool and output compatibility.',max_turns=3,run_config=RunConfig(tracing_disabled=True)),timeout=90)
        print(json.dumps({'success':bool(called) and result.final_output.code=='uteki-probe-2026','usage':asdict(result.context_wrapper.usage)},default=lambda obj:obj.model_dump(mode='json')))
    except Exception as exc:
        print(json.dumps({'success':False,'error_type':type(exc).__name__,'http_status':getattr(exc,'status_code',None),
             'frames':[(f.name,f.lineno) for f in traceback.extract_tb(exc.__traceback__)]}))

asyncio.run(main())
