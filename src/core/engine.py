"""
DoremiFa Xolatido — Core Engine
A practical implementation of the digital artist AI hub.

Architecture
------------

    User Idea
       ↓
    DoremiFaEngine  (Creative Orchestrator — the "brain")
       ↓
    Engine Registry (plugin architecture)
       ↓
    AudioEngine / VideoEngine / … (BaseEngine subclasses)
       ↓
    ProjectManager  (state / persistence)
       ↓
    ExportManager   (render → reality)

The Creative Router sits between the orchestrator and the registry,
automatically selecting the right engine(s) from a natural-language prompt.
"""

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base_engine import BaseEngine
from .creative_memory import CreativeMemory
from .creative_router import CreativeRouter
from .engine_types import GenerationParams, MediaType, Project
from .export_manager import ExportManager
from .project_manager import ProjectManager

logger = logging.getLogger("doremifa")


# ---------------------------------------------------------------------------
# Stub model helpers (used when neither a local model nor an API is available)
# ---------------------------------------------------------------------------

def _stub_output_path(media_type: str, prompt: str, ext: str) -> str:
    """Return a deterministic-ish path for stub / test output."""
    slug = re.sub(r"[^a-z0-9]+", "_", prompt.lower())[:40]
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    name = f"{slug}_{ts}.{ext}"
    out_dir = os.path.join("output", media_type)
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, name)


class _StubAudioModel:
    """Write a silent WAV stub — no ML dependencies required."""

    def generate(
        self,
        prompt: str,
        duration: float = 30.0,
        style: str = "default",
        quality: str = "standard",
        seed: Optional[int] = None,
    ) -> str:
        out = _stub_output_path("audio", prompt, "wav")
        _write_silent_wav(out, duration)
        return out

    @staticmethod
    def extract_features(path: str) -> Dict[str, Any]:
        return {"bpm": 120, "key": "C", "energy": 0.5}


class _StubVideoModel:
    """Write an empty MP4 placeholder — no ML dependencies required."""

    def generate(
        self,
        prompt: str,
        duration: float = 30.0,
        style: str = "default",
        quality: str = "standard",
        seed: Optional[int] = None,
        audio_features: Optional[Dict] = None,
    ) -> str:
        out = _stub_output_path("video", prompt, "mp4")
        with open(out, "wb") as fh:
            fh.write(b"")
        return out


def _write_silent_wav(path: str, duration: float) -> None:
    """Write the minimal headers for a valid 44100 Hz 16-bit mono WAV."""
    import struct
    sample_rate = 44100
    num_channels = 1
    bits_per_sample = 16
    num_samples = int(sample_rate * duration)
    data_size = num_samples * num_channels * (bits_per_sample // 8)
    with open(path, "wb") as fh:
        # RIFF header
        fh.write(b"RIFF")
        fh.write(struct.pack("<I", 36 + data_size))
        fh.write(b"WAVE")
        # fmt chunk
        fh.write(b"fmt ")
        fh.write(struct.pack("<IHHIIHH", 16, 1, num_channels, sample_rate,
                              sample_rate * num_channels * bits_per_sample // 8,
                              num_channels * bits_per_sample // 8,
                              bits_per_sample))
        # data chunk
        fh.write(b"data")
        fh.write(struct.pack("<I", data_size))
        fh.write(b"\x00" * data_size)


# ---------------------------------------------------------------------------
# AudioEngine
# ---------------------------------------------------------------------------

class AudioEngine(BaseEngine):
    """
    Audio generation and processing engine.

    Attempts to load a local ML model first; falls back to an external
    API stub if the model directory is absent or loading fails.
    """

    def __init__(
        self,
        provider: str = "local",
        model_path: str = "models/audio",
        device: str = "auto",
    ):
        self.provider = provider
        self.model_path = model_path
        self.device = device
        self._model = None
        self._load_model()

    # --- BaseEngine interface -------------------------------------------

    def generate(self, params: GenerationParams) -> str:
        out = params.output_path or _stub_output_path(
            "audio", params.prompt, "wav"
        )
        result = self._model.generate(
            prompt=params.prompt,
            duration=params.duration,
            style=params.style,
            quality=params.quality,
            seed=params.seed,
        )
        # If model returned a path (stub) use it, else assume *out* was filled
        return result if isinstance(result, str) else out

    def health_check(self) -> bool:
        return self._model is not None

    def capabilities(self) -> Dict[str, Any]:
        return {
            "media_type": MediaType.AUDIO.value,
            "provider": self.provider,
            "formats": ["wav", "mp3", "flac"],
            "quality_levels": ["low", "standard", "high"],
            "max_duration_seconds": 600,
        }

    # --- Extra public method used by the orchestrator ------------------

    def extract_features(self, path: str) -> Dict[str, Any]:
        return self._model.extract_features(path)

    # --- Internal ----------------------------------------------------------

    def _load_model(self) -> None:
        if self.provider == "local" and os.path.isdir(self.model_path):
            try:
                self._model = self._load_local_model()
                logger.info("AudioEngine: local model loaded from %s", self.model_path)
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "AudioEngine: could not load local model (%s); "
                    "falling back to stub",
                    exc,
                )
        logger.info("AudioEngine: using stub model")
        self._model = _StubAudioModel()
        self.provider = "stub"

    def _load_local_model(self):  # noqa: ANN201
        """Hook for subclasses / real implementations."""
        raise NotImplementedError("No local audio model implementation")


# ---------------------------------------------------------------------------
# VideoEngine
# ---------------------------------------------------------------------------

class VideoEngine(BaseEngine):
    """
    Video generation engine.

    Mirrors the graceful-degradation pattern of :class:`AudioEngine`.
    """

    def __init__(
        self,
        provider: str = "local",
        model_path: str = "models/video",
        device: str = "auto",
    ):
        self.provider = provider
        self.model_path = model_path
        self.device = device
        self._model = None
        self._load_model()

    # --- BaseEngine interface -------------------------------------------

    def generate(self, params: GenerationParams) -> str:
        result = self._model.generate(
            prompt=params.prompt,
            duration=params.duration,
            style=params.style,
            quality=params.quality,
            seed=params.seed,
        )
        return result if isinstance(result, str) else _stub_output_path(
            "video", params.prompt, "mp4"
        )

    def generate_synchronized(
        self, params: GenerationParams, audio_features: Dict[str, Any]
    ) -> str:
        """Generate video synchronised to the supplied audio features."""
        result = self._model.generate(
            prompt=params.prompt,
            duration=params.duration,
            style=params.style,
            quality=params.quality,
            seed=params.seed,
            audio_features=audio_features,
        )
        return result if isinstance(result, str) else _stub_output_path(
            "video", params.prompt, "mp4"
        )

    def health_check(self) -> bool:
        return self._model is not None

    def capabilities(self) -> Dict[str, Any]:
        return {
            "media_type": MediaType.VIDEO.value,
            "provider": self.provider,
            "formats": ["mp4", "webm"],
            "quality_levels": ["low", "standard", "high"],
            "max_duration_seconds": 300,
        }

    # --- Internal ----------------------------------------------------------

    def _load_model(self) -> None:
        if self.provider == "local" and os.path.isdir(self.model_path):
            try:
                self._model = self._load_local_model()
                logger.info("VideoEngine: local model loaded from %s", self.model_path)
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "VideoEngine: could not load local model (%s); "
                    "falling back to stub",
                    exc,
                )
        logger.info("VideoEngine: using stub model")
        self._model = _StubVideoModel()
        self.provider = "stub"

    def _load_local_model(self):  # noqa: ANN201
        raise NotImplementedError("No local video model implementation")


# ---------------------------------------------------------------------------
# DoremiFaEngine — The Creative Orchestrator
# ---------------------------------------------------------------------------

class DoremiFaEngine:
    """
    Core engine for DoremiFa Xolatido.

    Acts as the central orchestrator: manages a plugin registry of
    :class:`BaseEngine` instances, routes prompts through the
    :class:`CreativeRouter`, maintains project state via
    :class:`ProjectManager`, and remembers the artist's creative
    preferences through :class:`CreativeMemory`.
    """

    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)

        # Plugin registry — populated by _init_components and extendable
        # via register_engine()
        self.engines: Dict[str, BaseEngine] = {}

        # Project state
        self.projects: Dict[str, Dict] = {}
        self.active_project: Optional[str] = None

        # Initialise all subsystems
        self._init_components()

    # ------------------------------------------------------------------
    # Engine registry (plugin architecture)
    # ------------------------------------------------------------------

    def register_engine(self, name: str, engine: BaseEngine) -> None:
        """
        Register a generation engine under *name*.

        After registration the engine is immediately available to the
        creative router and to all generation methods.

        Example::

            engine.register_engine("lyrics", LyricsEngine())
        """
        if not isinstance(engine, BaseEngine):
            raise TypeError(
                f"Engine must be a BaseEngine subclass; got {type(engine)}"
            )
        self.engines[name] = engine
        self.creative_router.engines[name] = engine
        logger.info("Engine registered: %s (%s)", name, type(engine).__name__)

    # ------------------------------------------------------------------
    # Project management
    # ------------------------------------------------------------------

    def create_project(self, name: str) -> str:
        """Create a new project and set it as the active one."""
        project_id = self.project_manager.create_project(name)
        self.projects[project_id] = self.project_manager.get_project(project_id)
        self.active_project = project_id
        return project_id

    def get_project(self, project_id: str) -> Dict:
        """Return project details dict."""
        if project_id not in self.projects:
            raise ValueError(f"Project {project_id!r} not found")
        return self.project_manager.get_project(project_id)

    def get_projects(self) -> List[Dict]:
        """Return all projects."""
        return [self.project_manager.get_project(pid) for pid in self.projects]

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate_audio(
        self, params: GenerationParams, project_id: Optional[str] = None
    ) -> str:
        """Generate audio content. Returns track id or output path."""
        self._assert_project(project_id)
        engine: AudioEngine = self.engines["audio"]  # type: ignore[assignment]
        output_path = engine.generate(params)

        if project_id:
            return self.project_manager.add_audio_track(
                project_id, output_path, params.prompt
            )
        return output_path

    def generate_video(
        self, params: GenerationParams, project_id: Optional[str] = None
    ) -> str:
        """Generate video content. Returns track id or output path."""
        self._assert_project(project_id)
        engine: VideoEngine = self.engines["video"]  # type: ignore[assignment]
        output_path = engine.generate(params)

        if project_id:
            return self.project_manager.add_video_track(
                project_id, output_path, params.prompt
            )
        return output_path

    def generate_music_video(
        self, params: GenerationParams, project_id: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate synchronised audio + video ("Multimodal Composition").

        Returns a dict with keys ``audio_path``, ``video_path``, and
        (if a project is given) ``audio_track_id`` / ``video_track_id``.
        """
        self._assert_project(project_id)
        audio_engine: AudioEngine = self.engines["audio"]  # type: ignore[assignment]
        video_engine: VideoEngine = self.engines["video"]  # type: ignore[assignment]

        # 1. Generate audio
        audio_path = audio_engine.generate(params)

        # 2. Extract features for synchronisation
        audio_features = audio_engine.extract_features(audio_path)

        # 3. Generate video locked to audio
        video_path = video_engine.generate_synchronized(params, audio_features)

        result: Dict[str, str] = {
            "audio_path": audio_path,
            "video_path": video_path,
        }

        if project_id:
            result["audio_track_id"] = self.project_manager.add_audio_track(
                project_id, audio_path, params.prompt
            )
            result["video_track_id"] = self.project_manager.add_video_track(
                project_id, video_path, params.prompt
            )

        return result

    def generate_from_prompt(self, prompt: str, **kwargs: Any) -> List[str]:
        """
        Let the Creative Router decide which engine(s) handle *prompt*.

        Extra keyword arguments are forwarded to :class:`GenerationParams`.
        Returns a list of output paths / track ids.
        """
        engines = self.creative_router.route(prompt)
        if not engines:
            raise RuntimeError("No engines available to handle the prompt")

        params = GenerationParams(prompt=prompt, **kwargs)
        results: List[str] = []
        for engine in engines:
            output = engine.generate(params)
            results.append(output)
        return results

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_project(
        self, project_id: str, fmt: str = "mp4", quality: str = "standard"
    ) -> str:
        """Export project to file. Returns the output path."""
        if project_id not in self.projects:
            raise ValueError(f"Project {project_id!r} not found")
        # Always fetch the latest project data so that tracks added after
        # the project was first created are included in the export.
        project = self.project_manager.get_project(project_id)
        return self.export_manager.export(project, fmt, quality)

    # ------------------------------------------------------------------
    # Creative memory
    # ------------------------------------------------------------------

    def remember(self, key: str, value: Any) -> None:
        """Store a creative preference (e.g. preferred BPM)."""
        self.creative_memory.set(key, value)

    def recall(self, key: str, default: Any = None) -> Any:
        """Recall a stored creative preference."""
        return self.creative_memory.get(key, default)

    # ------------------------------------------------------------------
    # Engine health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, bool]:
        """Return a health-check result for every registered engine."""
        return {name: engine.health_check() for name, engine in self.engines.items()}

    def engine_capabilities(self) -> Dict[str, Any]:
        """Return capabilities dict for every registered engine."""
        return {
            name: engine.capabilities() for name, engine in self.engines.items()
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_config(self, config_path: str) -> Dict:
        default: Dict[str, Any] = {
            "models": {
                "audio": {
                    "provider": "local",
                    "model_path": "models/audio",
                    "device": "auto",
                },
                "video": {
                    "provider": "local",
                    "model_path": "models/video",
                    "device": "auto",
                },
            },
            "output": {
                "output_dir": "output",
                "default_format": {"audio": "wav", "video": "mp4"},
                "quality": {"audio": "standard", "video": "standard"},
            },
            "api": {"host": "0.0.0.0", "port": 8000, "enable_cors": True},
            "ui": {"theme": "dark", "language": "en"},
            "memory": {"path": "creative_memory.json"},
            "projects": {"dir": "projects"},
        }

        if os.path.exists(config_path):
            try:
                import json
                with open(config_path) as fh:
                    user_config = json.load(fh)
                for key, value in user_config.items():
                    if key in default and isinstance(default[key], dict) and isinstance(value, dict):
                        default[key].update(value)
                    else:
                        default[key] = value
                logger.info("Config loaded from %s", config_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not read config (%s); using defaults", exc)

        return default

    def _init_components(self) -> None:
        """Instantiate and wire all subsystems."""
        try:
            audio_cfg = self.config["models"]["audio"]
            video_cfg = self.config["models"]["video"]

            # Core engines
            audio_engine = AudioEngine(
                provider=audio_cfg["provider"],
                model_path=audio_cfg["model_path"],
                device=audio_cfg["device"],
            )
            video_engine = VideoEngine(
                provider=video_cfg["provider"],
                model_path=video_cfg["model_path"],
                device=video_cfg["device"],
            )

            # Register built-in engines
            self.engines["audio"] = audio_engine
            self.engines["video"] = video_engine

            # Creative router (aware of the registry)
            self.creative_router = CreativeRouter(self.engines)

            # Project management
            self.project_manager = ProjectManager(
                projects_dir=self.config["projects"]["dir"]
            )

            # Export pipeline
            self.export_manager = ExportManager(self.config["output"])

            # Creative memory (persistent taste)
            self.creative_memory = CreativeMemory(
                memory_path=self.config["memory"]["path"]
            )

            logger.info("All DoremiFa components initialised successfully")
        except Exception as exc:
            logger.error("Failed to initialise components: %s", exc)
            raise

    def _assert_project(self, project_id: Optional[str]) -> None:
        if project_id is not None and project_id not in self.projects:
            raise ValueError(f"Project {project_id!r} not found")
