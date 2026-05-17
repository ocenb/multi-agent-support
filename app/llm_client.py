import json
import os
from typing import Any, Literal

from dotenv import load_dotenv

Route = Literal["INFO", "STATUS", "BUG"]

load_dotenv()

DISPATCHER_SYSTEM_PROMPT = (
    "Ты маршрутизатор запросов поддержки. "
    "Верни JSON с полями: route, confidence, reason. "
    "route должен быть строго одним из INFO, STATUS, BUG. "
    "confidence должен быть числом от 0 до 1. "
    "reason - короткая причина на русском."
)


def _normalize_route(value: str) -> Route | None:
    up = value.strip().upper()
    if up in {"INFO", "STATUS", "BUG"}:
        return up  # type: ignore[return-value]
    return None


def classify_route_with_llm(message: str) -> tuple[Route, float, str] | None:
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-120b:free")
    if not openrouter_api_key:
        return None

    try:
        from openai import OpenAI
    except Exception:
        return None

    client = OpenAI(
        api_key=openrouter_api_key,
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        default_headers={
            "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost"),
            "X-Title": os.getenv("OPENROUTER_APP_NAME", "multi-agent-support-system"),
        },
    )

    try:
        resp = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": DISPATCHER_SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            temperature=0,
        )
        raw = resp.output_text.strip()
        payload: dict[str, Any] = json.loads(raw)
        route = _normalize_route(str(payload.get("route", "")))
        if route is None:
            return None
        confidence_raw = payload.get("confidence", 0.0)
        confidence = float(confidence_raw)
        if confidence < 0:
            confidence = 0.0
        if confidence > 1:
            confidence = 1.0
        reason = str(payload.get("reason", "LLM dispatcher"))
        return (route, confidence, reason)
    except Exception:
        return None
