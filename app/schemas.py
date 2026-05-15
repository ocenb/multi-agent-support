from typing import Literal

from pydantic import BaseModel

Route = Literal["INFO", "STATUS", "BUG"]
Action = Literal["ANSWER", "ASK_CLARIFY", "ESCALATE"]
ReasonCode = Literal["LOW_CONFIDENCE", "POLICY_RISK", "NO_KB_HIT", "TOOL_FAILURE"]


class InferenceRequest(BaseModel):
    message: str
    session_id: str | None = None
    thread_id: str | None = None
    user_id: str | None = None


class InferenceResponse(BaseModel):
    route: Route
    action: Action
    answer: str
    reason_code: ReasonCode | None = None


class OrderResponse(BaseModel):
    order_id: str
    status: Literal["processing", "shipped", "delivered", "canceled"]
    eta: str | None = None


class TicketPayload(BaseModel):
    title: str
    description: str
    priority: Literal["High", "Medium", "Low"]
    repro_steps: str
    expected: str
    actual: str


class TicketCreateResponse(BaseModel):
    ticket_id: str
    status: Literal["created"]
