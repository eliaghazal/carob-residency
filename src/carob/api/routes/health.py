from fastapi import APIRouter

router = APIRouter(tags=["ops"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness: the process is up and serving."""
    return {"status": "ok"}
