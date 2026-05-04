"""
DoremiFa Xolatido — Export Manager
Assembles project tracks and writes the final deliverable.
"""

import logging
import os
import shutil
from typing import Any, Dict

logger = logging.getLogger("doremifa.export_manager")


class ExportManager:
    """
    Combines audio and video tracks from a project into a single export.

    In production this would invoke FFmpeg (or equivalent) to mux the
    tracks.  The current implementation copies / stubs the output so the
    rest of the system can be exercised without media-processing
    dependencies.
    """

    def __init__(self, output_config: Dict[str, Any]):
        self.output_config = output_config
        self.output_dir = output_config.get("output_dir", "output")
        os.makedirs(self.output_dir, exist_ok=True)

    def export(self, project: Dict, fmt: str = "mp4", quality: str = "standard") -> str:
        """
        Export *project* to a file.

        Parameters
        ----------
        project:
            Plain dict as returned by :meth:`ProjectManager.get_project`.
        fmt:
            Target container format (``"mp4"``, ``"wav"``, ``"mp3"`` …).
        quality:
            ``"low"``, ``"standard"``, or ``"high"``.

        Returns
        -------
        str
            Absolute path to the exported file.
        """
        project_id = project["id"]
        out_path = os.path.join(self.output_dir, f"{project_id}.{fmt}")

        audio_tracks = project.get("audio_tracks", [])
        video_tracks = project.get("video_tracks", [])

        if not audio_tracks and not video_tracks:
            raise ValueError(
                f"Project {project_id!r} has no tracks to export"
            )

        # Prefer the first available track as the source file so that the
        # export at least produces a real file in test / stub scenarios.
        source_path: str | None = None
        for track in video_tracks + audio_tracks:
            candidate = track.get("path", "")
            if os.path.exists(candidate):
                source_path = candidate
                break

        if source_path:
            shutil.copy2(source_path, out_path)
        else:
            # Write a placeholder so callers always receive a path to a
            # real file even when no generated media is present yet.
            with open(out_path, "wb") as fh:
                fh.write(b"")

        logger.info(
            "Exported project %s → %s (format=%s quality=%s)",
            project_id,
            out_path,
            fmt,
            quality,
        )
        return out_path
