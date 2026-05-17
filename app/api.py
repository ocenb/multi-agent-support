from typing import Literal, cast

from fastapi import FastAPI, HTTPException, Response

from app.pipeline import ORDER_DB, handle_message
from app.schemas import (
    InferenceRequest,
    InferenceResponse,
    OrderResponse,
    TicketCreateResponse,
    TicketPayload,
)

app = FastAPI(title="Multi-Agent Support System Mock API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/order/{order_id}", response_model=OrderResponse)
def get_order(order_id: str, response: Response) -> OrderResponse:
    if order_id == "9999":
        response.status_code = 503
        return OrderResponse(
            order_id=order_id,
            status=None,
            eta=None,
            detail="Order service unavailable",
        )
    data = ORDER_DB.get(order_id)
    if data is None:
        response.status_code = 404
        return OrderResponse(
            order_id=order_id,
            status=None,
            eta=None,
            detail="Order not found",
        )
    status = cast(Literal["processing", "shipped", "delivered", "canceled"], data["status"])
    return OrderResponse(order_id=order_id, status=status, eta=data.get("eta"))


@app.post("/ticket", response_model=TicketCreateResponse)
def create_ticket(payload: TicketPayload) -> TicketCreateResponse:
    if len(payload.description.strip()) < 10:
        raise HTTPException(status_code=422, detail="Ticket description too short")
    return TicketCreateResponse(ticket_id="SUP-204", status="created")


@app.post("/infer", response_model=InferenceResponse)
def infer(payload: InferenceRequest) -> InferenceResponse:
    return handle_message(payload.message)
