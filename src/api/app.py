"""
DoremiFa Xolatido — Thin API Layer
Exposes the core engine over HTTP so that desktop apps, web dashboards,
mobile clients, Discord bots, and automation agents can all share the
same creative brain.

Endpoints
---------
POST /generate      — Generate audio, video, or a music-video
POST /project       — Create a new project
GET  /project/{id}  — Retrieve project details
POST /export        — Export a project to a media file
GET  /health        — Engine health check
GET  /capabilities  — Engine capability report
"""

import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.core.engine import DoremiFaEngine
from src.core.engine_types import GenerationParams

# ---------------------------------------------------------------------------
# Application singleton
# ---------------------------------------------------------------------------

app = FastAPI(
    title="DoremiFa Xolatido API",
    description="The digital artist AI hub — one brain, many bodies.",
    version="1.0.0",
)

# CORS — allow all origins by default (override via config)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazily initialised engine (created on first request or at startup)
_engine: Optional[DoremiFaEngine] = None


def get_engine() -> DoremiFaEngine:
    global _engine  # noqa: PLW0603
    if _engine is None:
        config_path = os.environ.get("DOREMIFA_CONFIG", "config.json")
        _engine = DoremiFaEngine(config_path=config_path)
    return _engine


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    prompt: str
    media_type: str = Field(
        default="auto",
        description="'audio', 'video', 'music_video', or 'auto' (router decides)",
    )
    duration: float = 30.0
    style: str = "default"
    quality: str = "standard"
    seed: Optional[int] = None
    project_id: Optional[str] = None


class GenerateResponse(BaseModel):
    results: List[str]
    routed_to: Optional[str] = None


class CreateProjectRequest(BaseModel):
    name: str


class CreateProjectResponse(BaseModel):
    project_id: str


class ExportRequest(BaseModel):
    project_id: str
    format: str = "mp4"
    quality: str = "standard"


class ExportResponse(BaseModel):
    output_path: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest) -> GenerateResponse:
    """Generate media from a prompt."""
    engine = get_engine()
    params = GenerationParams(
        prompt=req.prompt,
        duration=req.duration,
        style=req.style,
        quality=req.quality,
        seed=req.seed,
    )

    try:
        media_type = req.media_type.lower()

        if media_type == "audio":
            result = engine.generate_audio(params, project_id=req.project_id)
            return GenerateResponse(results=[result], routed_to="audio")

        if media_type == "video":
            result = engine.generate_video(params, project_id=req.project_id)
            return GenerateResponse(results=[result], routed_to="video")

        if media_type == "music_video":
            mv = engine.generate_music_video(params, project_id=req.project_id)
            return GenerateResponse(
                results=[mv["audio_path"], mv["video_path"]],
                routed_to="music_video",
            )

        # "auto" — let the Creative Router decide
        results = engine.generate_from_prompt(
            req.prompt,
            duration=req.duration,
            style=req.style,
            quality=req.quality,
            seed=req.seed,
        )
        label = engine.creative_router.route_label(req.prompt)
        return GenerateResponse(results=results, routed_to=label)

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/project", response_model=CreateProjectResponse)
def create_project(req: CreateProjectRequest) -> CreateProjectResponse:
    """Create a new DoremiFa project."""
    engine = get_engine()
    try:
        project_id = engine.create_project(req.name)
        return CreateProjectResponse(project_id=project_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/project/{project_id}")
def get_project(project_id: str) -> Dict[str, Any]:
    """Return project details."""
    engine = get_engine()
    try:
        return engine.get_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects")
def list_projects() -> List[Dict[str, Any]]:
    """Return all projects."""
    engine = get_engine()
    return engine.get_projects()


@app.post("/export", response_model=ExportResponse)
def export_project(req: ExportRequest) -> ExportResponse:
    """Export a project to a media file."""
    engine = get_engine()
    try:
        output_path = engine.export_project(
            req.project_id, fmt=req.format, quality=req.quality
        )
        return ExportResponse(output_path=output_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/health")
def health() -> Dict[str, Any]:
    """Engine health report."""
    engine = get_engine()
    return {"status": "ok", "engines": engine.health_report()}


@app.get("/capabilities")
def capabilities() -> Dict[str, Any]:
    """Engine capability report."""
    engine = get_engine()
    return engine.engine_capabilities()
