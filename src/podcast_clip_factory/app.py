from __future__ import annotations

from pathlib import Path

import flet as ft

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):
        return False

from podcast_clip_factory.application.orchestrator import AppOrchestrator
from podcast_clip_factory.application.pipeline_executor import PipelineExecutor
from podcast_clip_factory.domain.clip_rules import ClipRuleConfig, ClipRuleEngine
from podcast_clip_factory.infrastructure.llm.fallback_client import HeuristicClipAnalyzer
from podcast_clip_factory.infrastructure.llm.gemini_client import GeminiClipAnalyzer
from podcast_clip_factory.infrastructure.render.ffmpeg_builder import FFmpegCommandBuilder
from podcast_clip_factory.infrastructure.render.local_renderer import LocalFFmpegRenderer
from podcast_clip_factory.infrastructure.render.subtitle_generator import SubtitleGenerator
from podcast_clip_factory.infrastructure.storage.artifact_store import ArtifactStore
from podcast_clip_factory.infrastructure.storage.sqlite_repo import SQLiteJobRepository
from podcast_clip_factory.infrastructure.transcriber.faster_whisper import FasterWhisperTranscriber
from podcast_clip_factory.infrastructure.transcriber.mlx_whisper import MLXWhisperTranscriber
from podcast_clip_factory.presentation.main_view import MainView
from podcast_clip_factory.utils.config import load_settings
from podcast_clip_factory.utils.logger import configure_logger, get_logger


def build_orchestrator(root_dir: Path) -> AppOrchestrator:
    load_dotenv(root_dir / ".env")
    configure_logger()
    logger = get_logger()
    settings = load_settings(root_dir)

    repo = SQLiteJobRepository(root_dir / "runs" / "jobs.db")
    store = ArtifactStore(root_dir / "runs")

    primary_transcriber = MLXWhisperTranscriber(
        model=settings.transcribe.mlx_model,
        word_timestamps=settings.transcribe.word_timestamps,
    )
    fallback_transcriber = FasterWhisperTranscriber(
        model=settings.transcribe.faster_model,
        word_timestamps=settings.transcribe.word_timestamps,
    )

    llm_analyzer = GeminiClipAnalyzer(
        api_key=settings.llm.gemini_api_key,
        model=settings.llm.gemini_model,
        prompt_path=root_dir / "prompts" / "clip_selector.md",
    )
    heuristic_analyzer = HeuristicClipAnalyzer()

    rule_engine = ClipRuleEngine(
        ClipRuleConfig(
            target_clips=settings.app.target_clips,
            min_clips=settings.app.min_clips,
            min_sec=settings.app.clip_min_sec,
            max_sec=settings.app.clip_max_sec,
            title_max_chars=settings.app.title_max_chars,
        )
    )

    renderer = LocalFFmpegRenderer(
        app_config=settings.app,
        command_builder=FFmpegCommandBuilder(settings.render),
        subtitle_generator=SubtitleGenerator(settings.subtitle),
    )

    executor = PipelineExecutor(
        settings=settings,
        repo=repo,
        store=store,
        primary_transcriber=primary_transcriber,
        fallback_transcriber=fallback_transcriber,
        analyzer=llm_analyzer,
        fallback_analyzer=heuristic_analyzer,
        rule_engine=rule_engine,
        renderer=renderer,
        logger=logger,
    )

    return AppOrchestrator(executor=executor, repo=repo, store=store, logger=logger)


def main() -> None:
    root_dir = Path(__file__).resolve().parents[2]
    orchestrator = build_orchestrator(root_dir)

    def _run(page: ft.Page) -> None:
        page.title = "ショート動画乱発ツール"
        page.window.width = 1180
        page.window.height = 900
        page.padding = 16
        page.scroll = ft.ScrollMode.AUTO
        page.add(MainView(page=page, orchestrator=orchestrator, logger=get_logger()))

    ft.app(target=_run)


if __name__ == "__main__":
    main()
