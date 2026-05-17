#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description="Call Langflow run API and print result")
    parser.add_argument("--flow-id", required=True, help="Langflow flow id")
    parser.add_argument(
        "--message",
        required=True,
        help="Input message passed to flow",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:7860",
        help="Langflow base URL",
    )
    parser.add_argument(
        "--input-type",
        default="chat",
        help="Langflow input_type (default: chat)",
    )
    parser.add_argument(
        "--output-type",
        default="chat",
        help="Langflow output_type (default: chat)",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="Optional Langflow API key (sent as Bearer token)",
    )
    args = parser.parse_args()

    url = f"{args.base_url.rstrip('/')}/api/v1/run/{args.flow_id}"
    payload = {
        "input_value": args.message,
        "input_type": args.input_type,
        "output_type": args.output_type,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if args.api_key:
        headers["Authorization"] = f"Bearer {args.api_key}"

    req = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP error {e.code} calling {url}", file=sys.stderr)
        print(error_body, file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"Connection error calling {url}: {e}", file=sys.stderr)
        return 1

    try:
        parsed = json.loads(raw)
        print(json.dumps(parsed, ensure_ascii=False, indent=2))
    except json.JSONDecodeError:
        print(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
