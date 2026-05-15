#!/usr/bin/env python3
import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Totals:
    total: int = 0
    passed: int = 0
    route_match: int = 0
    action_match: int = 0
    reason_match_applicable: int = 0
    reason_match: int = 0
    contains_match: int = 0
    forbidden_clear: int = 0


def _norm(s: str) -> str:
    return s.strip().lower()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSONL at {path}:{lineno}: {e}") from e
    return rows


def index_by_id(rows: list[dict[str, Any]], path: Path) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        case_id = row.get("id")
        if not case_id:
            raise ValueError(f"Missing 'id' in {path}")
        if case_id in indexed:
            raise ValueError(f"Duplicate id '{case_id}' in {path}")
        indexed[case_id] = row
    return indexed


def evaluate_case(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": expected.get("id"),
        "pass": True,
        "errors": [],
        "checks": {},
    }

    exp_route = _norm(expected.get("expected_route", ""))
    act_route = _norm(str(actual.get("route", "")))
    route_ok = exp_route == act_route
    result["checks"]["route_match"] = route_ok
    if not route_ok:
        result["pass"] = False
        result["errors"].append(f"route mismatch: expected={exp_route} actual={act_route}")

    exp_action = _norm(expected.get("expected_action", ""))
    act_action = _norm(str(actual.get("action", "")))
    action_ok = exp_action == act_action
    result["checks"]["action_match"] = action_ok
    if not action_ok:
        result["pass"] = False
        result["errors"].append(f"action mismatch: expected={exp_action} actual={act_action}")

    exp_reason = expected.get("expected_reason_code")
    reason_required = exp_reason is not None
    if reason_required:
        exp_reason_n = _norm(str(exp_reason))
        act_reason_n = _norm(str(actual.get("reason_code", "")))
        reason_ok = exp_reason_n == act_reason_n
    else:
        reason_ok = True
    result["checks"]["reason_match"] = reason_ok
    if reason_required and not reason_ok:
        result["pass"] = False
        result["errors"].append(
            f"reason_code mismatch: expected={exp_reason} actual={actual.get('reason_code')}"
        )

    answer = _norm(str(actual.get("answer", "")))
    required_parts = [_norm(x) for x in expected.get("expected_contains", [])]
    contains_ok = all(part in answer for part in required_parts)
    result["checks"]["contains_match"] = contains_ok
    if not contains_ok:
        result["pass"] = False
        result["errors"].append("answer missing expected fragments")

    forbidden_parts = [_norm(x) for x in expected.get("forbidden_contains", [])]
    forbidden_ok = all(part not in answer for part in forbidden_parts)
    result["checks"]["forbidden_clear"] = forbidden_ok
    if not forbidden_ok:
        result["pass"] = False
        result["errors"].append("answer contains forbidden fragments")

    return result


def summarize(results: list[dict[str, Any]], expected_rows: list[dict[str, Any]]) -> dict[str, Any]:
    totals = Totals(total=len(results))

    exp_by_id = {r["id"]: r for r in expected_rows}

    for r in results:
        checks = r["checks"]
        case_id = r["id"]
        if r["pass"]:
            totals.passed += 1
        if checks["route_match"]:
            totals.route_match += 1
        if checks["action_match"]:
            totals.action_match += 1

        exp_reason = exp_by_id[case_id].get("expected_reason_code")
        if exp_reason is not None:
            totals.reason_match_applicable += 1
            if checks["reason_match"]:
                totals.reason_match += 1

        if checks["contains_match"]:
            totals.contains_match += 1
        if checks["forbidden_clear"]:
            totals.forbidden_clear += 1

    def pct(num: int, den: int) -> float:
        return round((num / den * 100.0), 2) if den else 0.0

    return {
        "total": totals.total,
        "passed": totals.passed,
        "pass_rate": pct(totals.passed, totals.total),
        "route_accuracy": pct(totals.route_match, totals.total),
        "action_accuracy": pct(totals.action_match, totals.total),
        "reason_code_accuracy": pct(totals.reason_match, totals.reason_match_applicable),
        "contains_accuracy": pct(totals.contains_match, totals.total),
        "forbidden_clear_rate": pct(totals.forbidden_clear, totals.total),
        "reason_code_cases": totals.reason_match_applicable,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate model outputs against eval JSONL dataset."
    )
    parser.add_argument(
        "--dataset",
        required=True,
        type=Path,
        help="Path to expected dataset JSONL (e.g. datasets/eval_seed.jsonl)",
    )
    parser.add_argument(
        "--predictions",
        required=True,
        type=Path,
        help=(
            "Path to model predictions JSONL with fields: "
            "id, route, action, reason_code (optional), answer"
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional path to write detailed JSON report",
    )
    args = parser.parse_args()

    expected_rows = load_jsonl(args.dataset)
    prediction_rows = load_jsonl(args.predictions)

    expected = index_by_id(expected_rows, args.dataset)
    predictions = index_by_id(prediction_rows, args.predictions)

    missing = sorted(set(expected) - set(predictions))
    extra = sorted(set(predictions) - set(expected))

    if missing:
        raise ValueError(f"Missing predictions for ids: {', '.join(missing)}")
    if extra:
        raise ValueError(f"Unexpected prediction ids: {', '.join(extra)}")

    results: list[dict[str, Any]] = []
    for case_id in expected:
        results.append(evaluate_case(expected[case_id], predictions[case_id]))

    summary = summarize(results, expected_rows)

    print("=== Evaluation Summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    failed = [r for r in results if not r["pass"]]
    print(f"Failed cases: {len(failed)}/{len(results)}")
    if failed:
        for r in failed:
            print(f"- {r['id']}: {'; '.join(r['errors'])}")

    if args.report:
        payload = {"summary": summary, "results": results}
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Report written to: {args.report}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
