from typing import Any, Awaitable, Callable, Dict, List

class PipelineContext:
    def __init__(self, idempotency_key: str, payload: Dict[str, Any]):
        self.key = idempotency_key
        self.payload = payload
        self.request_hash: str = ""
        self.response_body: Dict[str, Any] = {}
        self.status_code: int = 200
        self.headers: Dict[str, str] = {}
        self.is_served_from_cache: bool = False

MiddlewareFunc = Callable[[PipelineContext, Callable[[], Awaitable[None]]], Awaitable[None]]

class Pipeline:
    def __init__(self, middlewares: List[MiddlewareFunc]):
        self.middlewares = middlewares

    async def execute(self, ctx: PipelineContext) -> None:
        async def _next(index: int) -> None:
            if index < len(self.middlewares):
                await self.middlewares[index](ctx, lambda: _next(index + 1))
        
        await _next(0)