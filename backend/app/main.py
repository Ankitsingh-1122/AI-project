import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from .config import settings
from .database import Base, SessionLocal, engine
from .models import User
from .routers import admin, ai, auth, feedback, labels, notifications, problems, teams
from .pipeline import invalidate_cache

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(
    title="Civic Problem Platform API",
    description="AI-powered citizen problem deduplication, clustering and student-team matching.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(problems.router)
app.include_router(ai.router)
app.include_router(teams.router)
app.include_router(feedback.router)
app.include_router(notifications.router)
app.include_router(admin.router)
app.include_router(labels.router)


@app.middleware("http")
async def audit_unauthorized(request: Request, call_next):
    """Log exactly which auth channels a 401 request carried.

    Proxied clients (e.g. the preview sandbox) may strip request headers;
    this audit line shows whether the Authorization header, the X-Civic-Token
    header and/or the civic_token cookie survived the proxy.
    """
    response = await call_next(request)
    if response.status_code == 401 and request.url.path.startswith("/api"):
        h = request.headers
        cookie = h.get("cookie", "")
        log.warning(
            "401 AUDIT %s %s | authorization=%s x_civic_token=%s civic_cookie=%s ua=%s",
            request.method,
            request.url.path,
            bool(h.get("authorization")),
            bool(h.get("x-civic-token")),
            "civic_token=" in cookie,
            (h.get("user-agent") or "")[:60],
        )
    return response

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    if settings.SEED_ON_START:
        db = SessionLocal()
        try:
            from .seed import seed_if_empty

            if seed_if_empty(db):
                log.info("Database seeded with demo data.")
        finally:
            db.close()
    invalidate_cache()


@app.get("/api/health")
def health():
    return {"status": "ok", "embedder": settings.EMBEDDER}


@app.get("/api/stats/summary")
def public_summary():
    """Public landing-page numbers (no auth)."""
    from .models import Match, Problem, ProblemCluster, Team

    db = SessionLocal()
    try:
        problems = db.scalars(select(Problem)).all()
        return {
            "total_problems": len(problems),
            "duplicates_detected": sum(1 for p in problems if p.is_duplicate),
            "clusters": db.scalars(select(ProblemCluster)).all().__len__(),
            "teams": db.scalars(select(Team)).all().__len__(),
            "recommendations": db.scalars(select(Match)).all().__len__(),
        }
    finally:
        db.close()


# ---- Static frontend (Vite build) with SPA fallback ------------------------

if os.path.isdir(FRONTEND_DIST):
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        candidate = os.path.join(FRONTEND_DIST, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        index = FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
        # Never cache the app shell: asset files are hash-named, so a fresh
        # index.html always points browsers at the newest JS bundle.
        index.headers["Cache-Control"] = "no-cache"
        return index
