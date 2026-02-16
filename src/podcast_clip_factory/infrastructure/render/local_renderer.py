from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from podcast_clip_factory.domain.models import ClipCandidate, RenderedClip, Transcript
from podcast_clip_factory.infrastructure.render.ffmpeg_builder import FFmpegCommandBuilder
from podcast_clip_factory.infrastructure.render.subtitle_generator import SubtitleGenerator
from podcast_clip_factory.utils.config import AppConfig
from podcast_clip_factory.utils.media import run_command
from podcast_clip_factory.utils.paths import sanitize_filename


class LocalFFmpegRenderer:
    def __init__(
        self,
        app_config: AppConfig,
        command_builder: FFmpegCommandBuilder,
        subtitle_generator: SubtitleGenerator,
    ) -> None:
        self.app_config = app_config
        self.command_builder = command_builder
        self.subtitle_generator = subtitle_generator

    def render(
        self,
        input_video: Path,
        output_dir: Path,
        candidates: list[ClipCandidate],
        transcript: Transcript,
        on_event: Callable[[str, int, int, str], None] | None = None,
    ) -> list[RenderedClip]:
        clips_dir = output_dir / "clips"
        subtitle_dir = output_dir / "subtitles"
        clips_dir.mkdir(parents=True, exist_ok=True)
        subtitle_dir.mkdir(parents=True, exist_ok=True)
        total = len(candidates)

        with ThreadPoolExecutor(max_workers=self.app_config.render_parallelism) as executor:
            future_map = {
                executor.submit(
                    self._render_one,
                    idx,
                    candidate,
                    input_video,
                    clips_dir,
                    subtitle_dir,
                    transcript,
                    total,
                    on_event,
                ): idx
                for idx, candidate in enumerate(candidates, start=1)
            }
            ordered: list[tuple[int, RenderedClip]] = []
            for future in as_completed(future_map):
                idx = future_map[future]
                rendered_clip = future.result()
                ordered.append((idx, rendered_clip))

        ordered.sort(key=lambda pair: pair[0])
        return [clip for _, clip in ordered]

    def _render_one(
        self,
        idx: int,
        candidate: ClipCandidate,
        input_video: Path,
        clips_dir: Path,
        subtitle_dir: Path,
        transcript: Transcript,
        total: int,
        on_event: Callable[[str, int, int, str], None] | None,
    ) -> RenderedClip:
        safe_title = sanitize_filename(candidate.title)
        clip_filename = f"clip_{idx:02d}_{safe_title}.mp4"
        subtitle_filename = f"clip_{idx:02d}.ass"
        output_path = clips_dir / clip_filename
        subtitle_path = subtitle_dir / subtitle_filename

        if on_event:
            on_event("started", idx, total, candidate.title)

        self.subtitle_generator.generate(subtitle_path, candidate, transcript)
        cmd = self.command_builder.build(input_video, output_path, subtitle_path, candidate)

        try:
            run_command(cmd)
        except Exception:
            try:
                fallback = self.command_builder.build(
                    input_video,
                    output_path,
                    subtitle_path,
                    candidate,
                    fallback_software_codec=True,
                )
                run_command(fallback)
            except Exception:
                if on_event:
                    on_event("failed", idx, total, candidate.title)
                raise

        if on_event:
            on_event("completed", idx, total, candidate.title)

        return RenderedClip(
            clip_id=candidate.clip_id,
            title=candidate.title,
            start_sec=candidate.start_sec,
            end_sec=candidate.end_sec,
            video_path=output_path,
            subtitle_path=subtitle_path,
        )
