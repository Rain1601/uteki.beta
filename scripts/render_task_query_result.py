"""Render saved query execution into readable Markdown, without model calls."""
import argparse
from pathlib import Path

from uteki.agents.data_query.report import write_question_report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(write_question_report(args.session, args.output))
