import asyncio
import logging

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routers import personality, profile, settings, vibe
from app.services.feedback_analyzer import process_pending_feedback

logger = logging.getLogger("vibe.main")

app = FastAPI(title="Vibe-Radar", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exc_handler(_: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail)}},
    )


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(vibe.router)
app.include_router(profile.router)
app.include_router(personality.router)
app.include_router(settings.router)

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/vibe.js")
async def vibe_js():
    return FileResponse(STATIC_DIR / "vibe.js", media_type="application/javascript")


FEEDBACK_INTERVAL_SECONDS = 300  # 5 minutes


async def _feedback_loop():
    """Background loop: analyze user feedback every 5 minutes."""
    await asyncio.sleep(10)  # wait for startup
    while True:
        try:
            await process_pending_feedback()
        except Exception as e:
            logger.warning("Feedback analyzer error: %s", e)
        await asyncio.sleep(FEEDBACK_INTERVAL_SECONDS)


@app.on_event("startup")
async def start_feedback_loop():
    asyncio.create_task(_feedback_loop())
