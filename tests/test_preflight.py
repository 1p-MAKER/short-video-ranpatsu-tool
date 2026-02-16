from pathlib import Path

from podcast_clip_factory.application.orchestrator import AppOrchestrator
from podcast_clip_factory.utils.config import (
    AppConfig,
    LLMConfig,
    RenderConfig,
    Settings,
    SubtitleConfig,
    TranscribeConfig,
)


class DummyExecutor:
    def __init__(self, settings):
        self.settings = settings


class DummyRepo:
    pass


class DummyStore:
    pass


class DummyLogger:
    pass


def _settings(require_cloud: bool, key: str) -> Settings:
    return Settings(
        app=AppConfig(12, 10, 30, 60, 28, 3, True, 1),
        transcribe=TranscribeConfig("mlx", "faster", True, "m", "f"),
        llm=LLMConfig("gemini", "heuristic", require_cloud, 0, True, "g", key, ""),
        render=RenderConfig(1080, 1920, 1080, 608, 40, "h264_videotoolbox", "aac", "192k"),
        subtitle=SubtitleConfig(False, "Hiragino Sans", 52, "&H0039C1FF", "&H00FFFFFF", "&H00000000", 220),
        root_dir=Path("."),
    )


def test_preflight_requires_video_and_key_when_cloud_required(tmp_path: Path):
    orch = AppOrchestrator(DummyExecutor(_settings(True, "")), DummyRepo(), DummyStore(), DummyLogger())
    errors = orch.preflight(None)
    assert any("入力動画" in e for e in errors)
    assert any("GEMINI_API_KEY" in e for e in errors)


def test_preflight_passes_with_existing_video_and_key(tmp_path: Path):
    video = tmp_path / "in.mp4"
    video.write_text("x", encoding="utf-8")
    orch = AppOrchestrator(DummyExecutor(_settings(True, "abc")), DummyRepo(), DummyStore(), DummyLogger())
    errors = orch.preflight(video)
    assert errors == []
