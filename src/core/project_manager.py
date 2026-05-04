"""
DoremiFa Xolatido — Project Manager
Handles creation, persistence, and retrieval of projects.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .engine_types import Project

logger = logging.getLogger("doremifa.project_manager")


class ProjectManager:
    """
    Manages the lifecycle of DoremiFa projects.

    Projects are persisted as JSON files inside *projects_dir* so they
    survive process restarts.
    """

    def __init__(self, projects_dir: str = "projects"):
        self.projects_dir = projects_dir
        os.makedirs(projects_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_project(self, name: str) -> str:
        """Create a new project and persist it. Returns the project id."""
        now = datetime.now(tz=timezone.utc).isoformat()
        project = Project(
            id=str(uuid.uuid4()),
            name=name,
            created_at=now,
            updated_at=now,
        )
        self._save(project)
        logger.info("Created project '%s' (id=%s)", name, project.id)
        return project.id

    def get_project(self, project_id: str) -> Dict:
        """Return the project as a plain dict (JSON-serialisable)."""
        project = self._load(project_id)
        return self._to_dict(project)

    def list_projects(self) -> List[Dict]:
        """Return all persisted projects."""
        projects = []
        for filename in os.listdir(self.projects_dir):
            if filename.endswith(".json"):
                pid = filename[:-5]
                try:
                    projects.append(self.get_project(pid))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Could not load project %s: %s", pid, exc)
        return projects

    def add_audio_track(self, project_id: str, path: str, prompt: str) -> str:
        """Attach an audio track to a project. Returns the track id."""
        project = self._load(project_id)
        track_id = str(uuid.uuid4())
        project.audio_tracks.append(
            {"id": track_id, "path": path, "prompt": prompt}
        )
        project.updated_at = datetime.now(tz=timezone.utc).isoformat()
        self._save(project)
        return track_id

    def add_video_track(self, project_id: str, path: str, prompt: str) -> str:
        """Attach a video track to a project. Returns the track id."""
        project = self._load(project_id)
        track_id = str(uuid.uuid4())
        project.video_tracks.append(
            {"id": track_id, "path": path, "prompt": prompt}
        )
        project.updated_at = datetime.now(tz=timezone.utc).isoformat()
        self._save(project)
        return track_id

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _project_path(self, project_id: str) -> str:
        return os.path.join(self.projects_dir, f"{project_id}.json")

    def _save(self, project: Project) -> None:
        with open(self._project_path(project.id), "w") as fh:
            json.dump(self._to_dict(project), fh, indent=2)

    def _load(self, project_id: str) -> Project:
        path = self._project_path(project_id)
        if not os.path.exists(path):
            raise ValueError(f"Project {project_id!r} not found")
        with open(path) as fh:
            data = json.load(fh)
        return Project(**data)

    @staticmethod
    def _to_dict(project: Project) -> Dict:
        return {
            "id": project.id,
            "name": project.name,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
            "audio_tracks": project.audio_tracks,
            "video_tracks": project.video_tracks,
            "metadata": project.metadata,
            "settings": project.settings,
        }
