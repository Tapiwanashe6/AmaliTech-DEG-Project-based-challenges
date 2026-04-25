from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse

from app.schemas import PaymentRequest
from app.pipeline.core import Pipeline, PipelineContext
from app.pipeline.middlewares import (
    response_middleware,
    idempotency_middleware,
    validation_middleware,
    processing_middleware
)
from app.state.machine import state_manager


router = APIRouter()


MAX_KEY_LENGTH = 255

payment_pipeline = Pipeline([
    response_middleware,
    idempotency_middleware,
    validation_middleware,
    processing_middleware
])


@router.post(
    "/process-payment",
    responses={
        200: {"description": "Payment succeeded (may be cached)"},
        400: {"description": "Validation error (missing key, bad JSON, bad body)"},
        409: {"description": "Idempotency-Key reused with a different body"},
        413: {"description": "Request body too large"},
        500: {"description": "Internal server error"},
    },
)
async def process_payment_route(
    payload: PaymentRequest,
    idempotency_key: str = Header(
        ..., 
        alias="Idempotency-Key",
        description="Unique identifier for the transaction to ensure exactly-once processing.",
        max_length=MAX_KEY_LENGTH,
    ),
) -> JSONResponse:
    key = idempotency_key.strip()

    ctx = PipelineContext(
        idempotency_key=key,
        payload={"amount": payload.amount, "currency": payload.currency}
    )

    await payment_pipeline.execute(ctx)

    return JSONResponse(
        status_code=ctx.status_code,
        content=ctx.response_body,
        headers=ctx.headers,
    )

@router.get(
    "/idempotency/{key}",
    responses={
        200: {"description": "State inspector"},
        404: {"description": "Key not found"},
    }
)
async def inspect_state_route(key: str) -> JSONResponse:
    entry = state_manager.get_entry(key)
    if not entry:
        raise HTTPException(status_code=404, detail="Key not found")
        
    return JSONResponse(
        content={
            "key": entry.key,
            "state": entry.state.value,
            "request_hash": entry.request_hash,
            "response": entry.response
        }
    )
