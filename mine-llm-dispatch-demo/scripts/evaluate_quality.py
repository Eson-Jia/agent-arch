from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.eval.offline_quality import run_offline_evaluation


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run offline quality evaluation cases.")
    parser.add_argument(
        "--cases",
        type=Path,
        default=project_root / "eval" / "cases" / "workflow_cases.json",
        help="Path to offline evaluation case file",
    )
    parser.add_argument(
        "--llm-provider",
        default="mock",
        help="LLM provider to use for offline evaluation",
    )
    args = parser.parse_args()

    result = run_offline_evaluation(args.cases, llm_provider=args.llm_provider)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
