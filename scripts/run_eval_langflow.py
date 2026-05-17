#!/usr/bin/env python3
import argparse
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

VALID_ROUTES = {"INFO", "STATUS", "BUG"}
VALID_ACTIONS = {"ANSWER", "ASK_CLARIFY", "ESCALATE"}
VALID_REASON_CODES = {"LOW_CONFIDENCE", "POLICY_RISK", "NO_KB_HIT", "TOOL_FAILURE"}

JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.IGNORECASE | re.DOTALL)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            text = line.strip()
            if not text:
                continue
            rows.append(json.loads(text))
    return rows


def _extract_message_text(payload: dict[str, Any]) -> str:
    try:
        return str(payload["outputs"][0]["outputs"][0]["results"]["message"]["text"])
    except (KeyError, IndexError, TypeError):
        return ""


def _parse_json_object(text: str) -> dict[str, Any] | None:
    raw = text.strip()
    if not raw:
        return None

    if raw.startswith("{") and raw.endswith("}"):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass

    match = JSON_BLOCK_RE.search(raw)
    if match:
        try:
            parsed = json.loads(match.group(1))
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass

    first = raw.find("{")
    last = raw.rfind("}")
    if first != -1 and last != -1 and first < last:
        candidate = raw[first : last + 1]
        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _normalize_route(value: Any) -> str | None:
    if value is None:
        return None
    route = str(value).strip().upper()
    return route if route in VALID_ROUTES else None


def _normalize_action(value: Any) -> str | None:
    if value is None:
        return None
    action = str(value).strip().upper()
    return action if action in VALID_ACTIONS else None


def _normalize_reason_code(value: Any) -> str | None:
    if value is None:
        return None
    reason_code = str(value).strip().upper()
    return reason_code if reason_code in VALID_REASON_CODES else None


def _parse_action_payload(message_text: str) -> dict[str, Any]:
    text = message_text.strip()
    if not text:
        return {
            "route": None,
            "action": "ESCALATE",
            "reason_code": "TOOL_FAILURE",
            "answer": "Langflow returned empty message output.",
        }

    parsed = _parse_json_object(text)
    if parsed is not None:
        route = _normalize_route(parsed.get("route"))
        action = _normalize_action(parsed.get("action"))
        reason_code = _normalize_reason_code(parsed.get("reason_code"))

        # Some flows put user-facing text in `reason`; keep `answer` as required output.
        answer_raw = parsed.get("answer")
        if not isinstance(answer_raw, str) or not answer_raw.strip():
            reason_raw = parsed.get("reason")
            answer = str(reason_raw).strip() if reason_raw is not None else ""
        else:
            answer = answer_raw.strip()

        if action is None:
            action = "ESCALATE"
            reason_code = "TOOL_FAILURE"
            if not answer:
                answer = "Flow returned JSON without valid action."
        elif action == "ESCALATE" and reason_code is None:
            reason_code = "TOOL_FAILURE"

        return {
            "route": route,
            "action": action,
            "reason_code": reason_code,
            "answer": answer if answer else text,
        }

    return {
        "route": None,
        "action": "ESCALATE",
        "reason_code": "TOOL_FAILURE",
        "answer": text,
    }


def call_langflow(
    base_url: str,
    flow_id: str,
    message: str,
    api_key: str,
    input_type: str,
    output_type: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/v1/run/{flow_id}"
    req_body = json.dumps(
        {
            "input_value": message,
            "input_type": input_type,
            "output_type": output_type,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        raw = resp.read().decode("utf-8")
    data: dict[str, Any] = json.loads(raw)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Run eval dataset through Langflow API")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--flow-id", required=True)
    parser.add_argument("--base-url", default="http://localhost:7860")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--input-type", default="chat")
    parser.add_argument("--output-type", default="chat")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=90,
        help="HTTP timeout for each Langflow request (seconds)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=1,
        help="Number of retries on timeout/temporary network failure",
    )
    parser.add_argument(
        "--use-expected-route",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Use expected_route from dataset when flow output does not provide route. "
            "Disabled by default to avoid evaluation leakage."
        ),
    )
    args = parser.parse_args()

    rows = load_jsonl(args.dataset)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    with args.out.open("w", encoding="utf-8") as out_f:
        for row in rows:
            case_id = str(row["id"])
            try:
                last_error: Exception | None = None
                lf_resp: dict[str, Any] | None = None
                attempts = args.max_retries + 1
                for _ in range(attempts):
                    try:
                        lf_resp = call_langflow(
                            base_url=args.base_url,
                            flow_id=args.flow_id,
                            message=str(row["message"]),
                            api_key=args.api_key,
                            input_type=args.input_type,
                            output_type=args.output_type,
                            timeout_seconds=args.timeout_seconds,
                        )
                        last_error = None
                        break
                    except (TimeoutError, urllib.error.URLError) as e:
                        last_error = e
                        continue

                if lf_resp is None:
                    raise last_error if last_error is not None else TimeoutError("Unknown timeout")

                text = _extract_message_text(lf_resp)
                parsed = _parse_action_payload(text)
                route = _normalize_route(parsed.get("route"))
                if (not route) and args.use_expected_route:
                    route = row.get("expected_route")
                pred = {
                    "id": case_id,
                    "route": route,
                    "action": _normalize_action(parsed.get("action")) or "ESCALATE",
                    "reason_code": _normalize_reason_code(parsed.get("reason_code")),
                    "answer": parsed.get("answer", text),
                }
            except (
                urllib.error.URLError,
                urllib.error.HTTPError,
                TimeoutError,
                json.JSONDecodeError,
            ) as e:
                pred = {
                    "id": case_id,
                    "route": row.get("expected_route") if args.use_expected_route else None,
                    "action": "ESCALATE",
                    "reason_code": "TOOL_FAILURE",
                    "answer": f"Langflow call failed: {e}",
                }

            out_f.write(json.dumps(pred, ensure_ascii=False) + "\n")

    print(f"Langflow predictions written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
