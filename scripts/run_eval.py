#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any

from app.pipeline import handle_message


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        rows.append(json.loads(text))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate predictions for eval dataset")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("datasets/eval_seed.jsonl"),
        help="Path to eval dataset JSONL",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("reports/predictions.jsonl"),
        help="Path to write predictions JSONL",
    )
    args = parser.parse_args()

    rows = load_jsonl(args.dataset)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    with args.out.open("w", encoding="utf-8") as f:
        for row in rows:
            result = handle_message(str(row["message"]))
            record = {
                "id": row["id"],
                "route": result.route,
                "action": result.action,
                "reason_code": result.reason_code,
                "answer": result.answer,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Predictions written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
