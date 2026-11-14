from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health", summary="Check backend process health")
async def health(request: Request) -> dict[str, str]:
    """Return process health without depending on external services."""
    return {"status": "ok", "request_id": request.state.request_id}
