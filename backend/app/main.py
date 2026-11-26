import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config, db
from .api.routes import router
from .data_loader import get_store


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    get_store()  # fail fast if the datasets are invalid
    yield


app = FastAPI(title="DietWise API", version="1.0.0", lifespan=lifespan)

# Handle Vercel serverless path rewrites
@app.middleware("http")
async def vercel_path_rewrite(request: Request, call_next):
    matched = request.headers.get("x-matched-path")
    if matched and request.scope.get("path") in ("/api/index.py", "/api/index"):
        request.scope["path"] = matched
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Support both /api/meta and /meta seamlessly
app.include_router(router, prefix="/api")
app.include_router(router)

# Serve the built frontend from the same process (single-port unified deployment)
_dist_candidate = os.getenv("FRONTEND_DIST")
if not _dist_candidate:
    for candidate in [
        config.BASE_DIR.parent / "frontend" / "dist",
        config.BASE_DIR / "frontend_dist",
        config.BASE_DIR / "dist",
    ]:
        if candidate.is_dir() and (candidate / "index.html").is_file():
            _dist_candidate = str(candidate)
            break

if _dist_candidate and Path(_dist_candidate).is_dir():
    app.mount("/", StaticFiles(directory=_dist_candidate, html=True), name="frontend")
else:
    @app.get("/")
    def root():
        return {"status": "ok", "app": "DietWise API", "docs": "/docs"}
