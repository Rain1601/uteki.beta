import argparse
import asyncio
import os
from pathlib import Path
from uteki.agents.analysis_comparison import run_comparison

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--model',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--provider',choices=['openai','aihubmix'],default='openai')
    args=p.parse_args()
    key='AIHUBMIX_API_KEY' if args.provider=='aihubmix' else 'OPENAI_API_KEY'
    if not os.environ.get(key):
        p.error('Configure '+key+' locally; do not put credentials in arguments.')
    asyncio.run(run_comparison(Path(__file__).resolve().parents[1],args.output,args.model,args.provider))
