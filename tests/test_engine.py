"""
Unit tests for DoremiFa Xolatido core components.

All tests run without ML dependencies — the engine stubs are sufficient.
"""

import json
import os
import shutil
import tempfile
import pytest

from src.core.base_engine import BaseEngine
from src.core.engine import AudioEngine, VideoEngine, DoremiFaEngine
from src.core.engine_types import GenerationParams, MediaType
from src.core.project_manager import ProjectManager
from src.core.export_manager import ExportManager
from src.core.creative_memory import CreativeMemory
from src.core.creative_router import CreativeRouter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def engine(tmp_dir):
    """Return a fully initialised DoremiFaEngine pointing at tmp dirs."""
    config = {
        "models": {
            "audio": {"provider": "stub", "model_path": os.path.join(tmp_dir, "models/audio"), "device": "cpu"},
            "video": {"provider": "stub", "model_path": os.path.join(tmp_dir, "models/video"), "device": "cpu"},
        },
        "output": {"output_dir": os.path.join(tmp_dir, "output")},
        "api": {"host": "0.0.0.0", "port": 8000, "enable_cors": True},
        "ui": {"theme": "dark", "language": "en"},
        "memory": {"path": os.path.join(tmp_dir, "creative_memory.json")},
        "projects": {"dir": os.path.join(tmp_dir, "projects")},
    }
    cfg_path = os.path.join(tmp_dir, "config.json")
    with open(cfg_path, "w") as fh:
        json.dump(config, fh)

    return DoremiFaEngine(config_path=cfg_path)


# ---------------------------------------------------------------------------
# BaseEngine — contract
# ---------------------------------------------------------------------------

class TestBaseEngine:
    def test_cannot_instantiate_abstract(self):
        """BaseEngine must not be directly instantiable."""
        with pytest.raises(TypeError):
            BaseEngine()  # type: ignore[abstract]

    def test_concrete_must_implement_all_methods(self):
        """A partial implementation must still raise TypeError."""
        class PartialEngine(BaseEngine):
            def generate(self, params):
                return ""

        with pytest.raises(TypeError):
            PartialEngine()  # type: ignore[abstract]

    def test_full_implementation_is_instantiable(self):
        class FullEngine(BaseEngine):
            def generate(self, params):
                return "output.wav"

            def health_check(self):
                return True

            def capabilities(self):
                return {"media_type": "test"}

        fe = FullEngine()
        assert fe.health_check()
        assert fe.capabilities()["media_type"] == "test"


# ---------------------------------------------------------------------------
# AudioEngine
# ---------------------------------------------------------------------------

class TestAudioEngine:
    def test_health_check_is_true(self):
        ae = AudioEngine()
        assert ae.health_check() is True

    def test_capabilities_contain_media_type(self):
        ae = AudioEngine()
        caps = ae.capabilities()
        assert caps["media_type"] == MediaType.AUDIO.value

    def test_generate_returns_existing_file(self, tmp_dir):
        ae = AudioEngine()
        params = GenerationParams(prompt="calm piano", duration=2.0,
                                  output_path=os.path.join(tmp_dir, "out.wav"))
        path = ae.generate(params)
        assert os.path.exists(path), f"Expected file at {path}"

    def test_extract_features_returns_dict(self, tmp_dir):
        ae = AudioEngine()
        params = GenerationParams(prompt="test", duration=1.0,
                                  output_path=os.path.join(tmp_dir, "feat.wav"))
        path = ae.generate(params)
        features = ae.extract_features(path)
        assert isinstance(features, dict)
        assert "bpm" in features


# ---------------------------------------------------------------------------
# VideoEngine
# ---------------------------------------------------------------------------

class TestVideoEngine:
    def test_health_check_is_true(self):
        ve = VideoEngine()
        assert ve.health_check() is True

    def test_capabilities_contain_media_type(self):
        ve = VideoEngine()
        assert ve.capabilities()["media_type"] == MediaType.VIDEO.value

    def test_generate_returns_existing_file(self, tmp_dir):
        ve = VideoEngine()
        params = GenerationParams(prompt="dark cinematic scene", duration=5.0,
                                  output_path=os.path.join(tmp_dir, "out.mp4"))
        path = ve.generate(params)
        assert os.path.exists(path), f"Expected file at {path}"

    def test_generate_synchronized(self, tmp_dir):
        ve = VideoEngine()
        params = GenerationParams(prompt="sync test", duration=5.0)
        path = ve.generate_synchronized(params, {"bpm": 120, "key": "C"})
        assert os.path.exists(path)


# ---------------------------------------------------------------------------
# ProjectManager
# ---------------------------------------------------------------------------

class TestProjectManager:
    def test_create_and_get_project(self, tmp_dir):
        pm = ProjectManager(projects_dir=os.path.join(tmp_dir, "projects"))
        pid = pm.create_project("My Album")
        data = pm.get_project(pid)
        assert data["name"] == "My Album"
        assert data["id"] == pid

    def test_add_audio_track(self, tmp_dir):
        pm = ProjectManager(projects_dir=os.path.join(tmp_dir, "projects"))
        pid = pm.create_project("Test")
        track_id = pm.add_audio_track(pid, "/tmp/test.wav", "lo-fi")
        project = pm.get_project(pid)
        assert len(project["audio_tracks"]) == 1
        assert project["audio_tracks"][0]["id"] == track_id

    def test_add_video_track(self, tmp_dir):
        pm = ProjectManager(projects_dir=os.path.join(tmp_dir, "projects"))
        pid = pm.create_project("Test")
        track_id = pm.add_video_track(pid, "/tmp/test.mp4", "cinematic")
        project = pm.get_project(pid)
        assert len(project["video_tracks"]) == 1
        assert project["video_tracks"][0]["id"] == track_id

    def test_list_projects(self, tmp_dir):
        pm = ProjectManager(projects_dir=os.path.join(tmp_dir, "projects"))
        pm.create_project("Alpha")
        pm.create_project("Beta")
        projects = pm.list_projects()
        names = {p["name"] for p in projects}
        assert "Alpha" in names
        assert "Beta" in names

    def test_project_persists(self, tmp_dir):
        proj_dir = os.path.join(tmp_dir, "projects")
        pm1 = ProjectManager(projects_dir=proj_dir)
        pid = pm1.create_project("Persistent")

        pm2 = ProjectManager(projects_dir=proj_dir)
        data = pm2.get_project(pid)
        assert data["name"] == "Persistent"

    def test_get_nonexistent_project_raises(self, tmp_dir):
        pm = ProjectManager(projects_dir=os.path.join(tmp_dir, "projects"))
        with pytest.raises(ValueError):
            pm.get_project("does-not-exist")


# ---------------------------------------------------------------------------
# ExportManager
# ---------------------------------------------------------------------------

class TestExportManager:
    def test_export_empty_project_raises(self, tmp_dir):
        em = ExportManager({"output_dir": tmp_dir})
        project = {
            "id": "test123",
            "audio_tracks": [],
            "video_tracks": [],
        }
        with pytest.raises(ValueError):
            em.export(project)

    def test_export_with_track_creates_file(self, tmp_dir):
        # Create a dummy source file
        src = os.path.join(tmp_dir, "source.wav")
        with open(src, "wb") as fh:
            fh.write(b"\x00" * 16)

        em = ExportManager({"output_dir": tmp_dir})
        project = {
            "id": "proj999",
            "audio_tracks": [{"id": "t1", "path": src, "prompt": "test"}],
            "video_tracks": [],
        }
        out = em.export(project, fmt="wav")
        assert os.path.exists(out)


# ---------------------------------------------------------------------------
# CreativeMemory
# ---------------------------------------------------------------------------

class TestCreativeMemory:
    def test_defaults_are_loaded(self, tmp_dir):
        mem = CreativeMemory(memory_path=os.path.join(tmp_dir, "mem.json"))
        assert mem.get("preferred_bpm") == 120

    def test_set_and_get(self, tmp_dir):
        mem = CreativeMemory(memory_path=os.path.join(tmp_dir, "mem.json"))
        mem.set("preferred_bpm", 140)
        assert mem.get("preferred_bpm") == 140

    def test_persists_across_instances(self, tmp_dir):
        path = os.path.join(tmp_dir, "mem.json")
        mem1 = CreativeMemory(memory_path=path)
        mem1.set("vocal_tone", "raspy")

        mem2 = CreativeMemory(memory_path=path)
        assert mem2.get("vocal_tone") == "raspy"

    def test_append_to_list(self, tmp_dir):
        mem = CreativeMemory(memory_path=os.path.join(tmp_dir, "mem.json"))
        mem.append_to_list("style_tags", "dark")
        mem.append_to_list("style_tags", "cinematic")
        assert "dark" in mem.get("style_tags")
        assert "cinematic" in mem.get("style_tags")

    def test_reset(self, tmp_dir):
        mem = CreativeMemory(memory_path=os.path.join(tmp_dir, "mem.json"))
        mem.set("preferred_bpm", 200)
        mem.reset()
        assert mem.get("preferred_bpm") == 120

    def test_all_returns_dict(self, tmp_dir):
        mem = CreativeMemory(memory_path=os.path.join(tmp_dir, "mem.json"))
        data = mem.all()
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# CreativeRouter
# ---------------------------------------------------------------------------

class TestCreativeRouter:
    @pytest.fixture
    def router_with_engines(self):
        ae = AudioEngine()
        ve = VideoEngine()
        return CreativeRouter({"audio": ae, "video": ve})

    def test_routes_audio_prompt(self, router_with_engines):
        engines = router_with_engines.route("make a lo-fi beat")
        names = [type(e).__name__ for e in engines]
        assert "AudioEngine" in names

    def test_routes_video_prompt(self, router_with_engines):
        engines = router_with_engines.route("create a cinematic video scene")
        names = [type(e).__name__ for e in engines]
        assert "VideoEngine" in names

    def test_routes_music_video(self, router_with_engines):
        engines = router_with_engines.route("dark cinematic trap music video")
        names = [type(e).__name__ for e in engines]
        assert "AudioEngine" in names
        assert "VideoEngine" in names

    def test_fallback_when_no_match(self, router_with_engines):
        engines = router_with_engines.route("something completely unrelated xyz")
        assert len(engines) >= 1

    def test_route_label(self, router_with_engines):
        assert router_with_engines.route_label("make a song") == "audio"
        assert router_with_engines.route_label("cinematic music video") == "music_video"

    def test_missing_engine_skipped_gracefully(self):
        # Only audio registered; video prompt should skip video
        ae = AudioEngine()
        router = CreativeRouter({"audio": ae})
        engines = router.route("cinematic music video")
        # Should still return the audio engine without crashing
        assert len(engines) >= 1


# ---------------------------------------------------------------------------
# DoremiFaEngine — integration
# ---------------------------------------------------------------------------

class TestDoremiFaEngine:
    def test_create_project(self, engine):
        pid = engine.create_project("Integration Test Album")
        assert pid
        assert engine.active_project == pid

    def test_get_project(self, engine):
        pid = engine.create_project("Fetch Me")
        data = engine.get_project(pid)
        assert data["name"] == "Fetch Me"

    def test_get_nonexistent_project_raises(self, engine):
        with pytest.raises(ValueError):
            engine.get_project("ghost-project-id")

    def test_generate_audio_standalone(self, engine, tmp_dir):
        params = GenerationParams(prompt="lo-fi chill", duration=2.0)
        path = engine.generate_audio(params)
        assert os.path.exists(path)

    def test_generate_audio_adds_track_to_project(self, engine):
        pid = engine.create_project("Audio Project")
        params = GenerationParams(prompt="trap beat", duration=2.0)
        track_id = engine.generate_audio(params, project_id=pid)
        project = engine.get_project(pid)
        assert any(t["id"] == track_id for t in project["audio_tracks"])

    def test_generate_video_standalone(self, engine):
        params = GenerationParams(prompt="dark cinematic", duration=3.0)
        path = engine.generate_video(params)
        assert os.path.exists(path)

    def test_generate_music_video(self, engine):
        params = GenerationParams(prompt="epic orchestral", duration=3.0)
        result = engine.generate_music_video(params)
        assert "audio_path" in result
        assert "video_path" in result
        assert os.path.exists(result["audio_path"])
        assert os.path.exists(result["video_path"])

    def test_generate_from_prompt_auto_route(self, engine):
        results = engine.generate_from_prompt("make a lo-fi song", duration=2.0)
        assert len(results) >= 1

    def test_register_custom_engine(self, engine):
        class LyricsEngine(BaseEngine):
            def generate(self, params):
                return "verse: " + params.prompt
            def health_check(self):
                return True
            def capabilities(self):
                return {"media_type": "lyrics"}

        engine.register_engine("lyrics", LyricsEngine())
        assert "lyrics" in engine.engines
        assert engine.health_report()["lyrics"] is True

    def test_health_report(self, engine):
        report = engine.health_report()
        assert "audio" in report
        assert "video" in report
        assert all(isinstance(v, bool) for v in report.values())

    def test_capabilities_report(self, engine):
        caps = engine.engine_capabilities()
        assert "audio" in caps
        assert "video" in caps

    def test_creative_memory_remember_recall(self, engine):
        engine.remember("preferred_bpm", 98)
        assert engine.recall("preferred_bpm") == 98

    def test_export_project_raises_if_no_tracks(self, engine):
        pid = engine.create_project("Empty")
        with pytest.raises(ValueError):
            engine.export_project(pid)

    def test_export_project_with_audio_track(self, engine, tmp_dir):
        # Produce a real audio file first
        params = GenerationParams(prompt="export test", duration=1.0)
        pid = engine.create_project("Export Album")
        engine.generate_audio(params, project_id=pid)
        out = engine.export_project(pid, fmt="wav")
        assert os.path.exists(out)
