"""
DoremiFa Xolatido — Shared data-types
Kept in a separate module so that base_engine.py can import them without
creating circular dependencies.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class MediaType(Enum):
    AUDIO = "audio"
    VIDEO = "video"
    PROJECT = "project"


@dataclass
class GenerationParams:
    """Common parameters for all generation tasks."""

    prompt: str
    duration: float = 30.0
    style: str = "default"
    quality: str = "standard"  # low | standard | high
    seed: Optional[int] = None
    output_path: Optional[str] = None


@dataclass
class Project:
    """In-memory representation of a DoremiFa project."""

    id: str
    name: str
    created_at: str
    updated_at: str
    audio_tracks: List[Dict] = field(default_factory=list)
    video_tracks: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    settings: Dict = field(default_factory=dict)
