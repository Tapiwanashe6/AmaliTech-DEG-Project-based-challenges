import asyncio
import secrets
from fastapi import HTTPException
from app.pipeline.core import PipelineContext
from app.state.machine import state_manager, State
from app.hashing import hash_body
from app.config import get_settings

async def validation_middleware(ctx: PipelineContext, next_call):
    if ctx.payload.get("amount", 0) <= 0:
        raise HTTPException(status_code=400, detail={"error": "invalid_amount", "message": "Amount must be positive"})
    await next_call()

async def idempotency_middleware(ctx: PipelineContext, next_call):
    ctx.request_hash = hash_body(ctx.payload)
    
    transition = state_manager.transition_to_processing(ctx.key, ctx.request_hash)
    entry = transition.entry
    
    if not transition.is_new:
        if entry.request_hash != ctx.request_hash:
            raise HTTPException(
                status_code=409, 
                detail={
                    "error": "idempotency_conflict",
                    "message": "Idempotency key mismatch detected"
                }
            )
            
        if entry.state == State.PROCESSING:
            if entry.future:
                ctx.response_body = await asyncio.shield(entry.future)
                ctx.headers["X-Cache-Hit"] = "true"
                ctx.is_served_from_cache = True
                return
                
        if entry.state == State.COMPLETED:
            assert entry.response is not None
            ctx.response_body = entry.response
            ctx.headers["X-Cache-Hit"] = "true"
            ctx.is_served_from_cache = True
            return
            
    try:
        await next_call()
        state_manager.transition_to_completed(ctx.key, ctx.response_body)
    except Exception as e:
        state_manager.transition_to_failed(ctx.key, e)
        raise

async def processing_middleware(ctx: PipelineContext, next_call):
    settings = get_settings()
    await asyncio.sleep(settings.payment_simulated_delay_seconds)
    ctx.response_body = {
        "status": "succeeded",
        "message": f"Charged {ctx.payload['amount']} {ctx.payload['currency']}",
        "chargeId": f"ch_{secrets.token_hex(8)}"
    }
    ctx.status_code = 200
    await next_call()

async def response_middleware(ctx: PipelineContext, next_call):
    await next_call()
    ctx.headers["X-Pipeline-Architecture"] = "true"