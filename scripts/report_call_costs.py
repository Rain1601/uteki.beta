"""Generate create-only cost report; historical backfill makes no model calls."""
import argparse
import json
from uteki.agents.runtime.call_costs import cost_report

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run')
    parser.add_argument('--backfill', action='store_true')
    args = parser.parse_args()
    print(json.dumps(cost_report(args.run, args.backfill), ensure_ascii=False))
