from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import re
import subprocess

from podcast_clip_factory.domain.models import (
    ClipCandidate,
    ImpactOverlayStyle,
    RenderedClip,
    TitleOverlayStyle,
    Transcript,
)
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
        enable_subtitles: bool = True,
    ) -> None:
        self.app_config = app_config
        self.command_builder = command_builder
        self.subtitle_generator = subtitle_generator
        self.enable_subtitles = enable_subtitles

    def render(
        self,
        input_video: Path,
        output_dir: Path,
        candidates: list[ClipCandidate],
        transcript: Transcript,
        title_style: TitleOverlayStyle | None = None,
        impact_style: ImpactOverlayStyle | None = None,
        on_event: Callable[[str, int, int, str], None] | None = None,
        cancel_event=None,
    ) -> list[RenderedClip]:
        clips_dir = output_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        subtitle_dir: Path | None = None
        if self.enable_subtitles:
            subtitle_dir = output_dir / "subtitles"
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
                    title_style,
                    impact_style,
                    total,
                    on_event,
                    cancel_event,
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
        subtitle_dir: Path | None,
        transcript: Transcript,
        title_style: TitleOverlayStyle | None,
        impact_style: ImpactOverlayStyle | None,
        total: int,
        on_event: Callable[[str, int, int, str], None] | None,
        cancel_event=None,
    ) -> RenderedClip:
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError("processing cancelled")

        safe_title = sanitize_filename(candidate.title)
        clip_filename = f"clip_{idx:02d}_{safe_title}.mp4"
        output_path = clips_dir / clip_filename
        subtitle_path: Path | None = None
        if self.enable_subtitles and subtitle_dir is not None:
            subtitle_filename = f"clip_{idx:02d}.ass"
            subtitle_path = subtitle_dir / subtitle_filename

        if on_event:
            on_event("started", idx, total, candidate.title)

        speech_intervals = (
            self._build_speech_intervals(input_video, candidate, transcript)
            if self.app_config.enable_silence_compaction
            else None
        )

        if subtitle_path is not None:
            self.subtitle_generator.generate(
                subtitle_path,
                candidate,
                transcript,
                speech_intervals=speech_intervals,
            )
        cmd = self.command_builder.build(
            input_video=input_video,
            output_video=output_path,
            subtitle_path=subtitle_path,
            candidate=candidate,
            title_style=title_style,
            impact_style=impact_style,
            speech_intervals=speech_intervals,
        )

        try:
            run_command(cmd, cancel_event=cancel_event)
        except Exception:
            try:
                fallback = self.command_builder.build(
                    input_video=input_video,
                    output_video=output_path,
                    subtitle_path=subtitle_path,
                    candidate=candidate,
                    title_style=title_style,
                    impact_style=impact_style,
                    speech_intervals=speech_intervals,
                    fallback_software_codec=True,
                )
                run_command(fallback, cancel_event=cancel_event)
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

    def _build_speech_intervals(
        self,
        input_video: Path,
        candidate: ClipCandidate,
        transcript: Transcript,
    ) -> list[tuple[float, float]] | None:
        duration = max(0.0, float(candidate.end_sec - candidate.start_sec))
        if duration <= 0:
            return None

        pad = max(0.0, float(self.app_config.silence_speech_pad_sec))
        merge_gap = max(0.0, float(self.app_config.silence_merge_gap_sec))
        min_seg = max(0.05, float(self.app_config.silence_min_segment_sec))
        min_cut_total = max(0.0, float(self.app_config.silence_min_cut_total_sec))
        max_segments = max(1, int(self.app_config.silence_max_segments))

        silences = self._detect_silence_ranges(input_video, candidate)
        if silences:
            speech = self._invert_intervals(silences, duration)
        else:
            speech = self._build_from_transcript_fallback(candidate, transcript, pad, min_seg)

        if len(speech) < 2:
            return None

        padded = [
            (max(0.0, start - pad), min(duration, end + pad))
            for start, end in speech
            if end - start >= min_seg
        ]
        merged = self._merge_intervals(padded, merge_gap)
        if len(merged) < 2:
            return None

        if len(merged) > max_segments:
            merged = self._reduce_intervals(merged, max_segments)

        original = duration
        kept = sum(max(0.0, end - start) for start, end in merged)
        if original - kept < min_cut_total:
            return None

        return merged

    def _detect_silence_ranges(self, input_video: Path, candidate: ClipCandidate) -> list[tuple[float, float]]:
        duration = max(0.0, float(candidate.end_sec - candidate.start_sec))
        if duration <= 0:
            return []

        noise_db = float(self.app_config.silence_detect_noise_db)
        min_silence = max(0.05, float(self.app_config.silence_detect_min_sec))
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-ss",
            f"{candidate.start_sec:.3f}",
            "-to",
            f"{candidate.end_sec:.3f}",
            "-i",
            str(input_video),
            "-vn",
            "-af",
            f"silencedetect=noise={noise_db:.1f}dB:d={min_silence:.2f}",
            "-f",
            "null",
            "-",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            return []

        text = (proc.stderr or "") + "\n" + (proc.stdout or "")
        silences: list[tuple[float, float]] = []
        current_start: float | None = None
        for line in text.splitlines():
            start_match = re.search(r"silence_start:\s*([0-9.]+)", line)
            if start_match:
                current_start = max(0.0, float(start_match.group(1)))
                continue
            end_match = re.search(r"silence_end:\s*([0-9.]+)", line)
            if end_match and current_start is not None:
                end_val = min(duration, float(end_match.group(1)))
                if end_val > current_start:
                    silences.append((current_start, end_val))
                current_start = None
        if current_start is not None and current_start < duration:
            silences.append((current_start, duration))
        return self._merge_intervals(silences, 0.03)

    def _invert_intervals(
        self,
        silences: list[tuple[float, float]],
        duration: float,
    ) -> list[tuple[float, float]]:
        if duration <= 0:
            return []
        result: list[tuple[float, float]] = []
        cursor = 0.0
        for start, end in sorted(silences, key=lambda x: x[0]):
            start = max(0.0, min(duration, start))
            end = max(0.0, min(duration, end))
            if start > cursor:
                result.append((cursor, start))
            cursor = max(cursor, end)
        if cursor < duration:
            result.append((cursor, duration))
        return result

    def _build_from_transcript_fallback(
        self,
        candidate: ClipCandidate,
        transcript: Transcript,
        _pad: float,
        min_seg: float,
    ) -> list[tuple[float, float]]:
        clip_start = float(candidate.start_sec)
        clip_end = float(candidate.end_sec)
        overlaps: list[tuple[float, float]] = []
        for seg in transcript.segments:
            if seg.end <= clip_start or seg.start >= clip_end:
                continue
            start = max(0.0, seg.start - clip_start)
            end = min(clip_end - clip_start, seg.end - clip_start)
            if end - start >= min_seg:
                overlaps.append((start, end))
        return overlaps

    def _merge_intervals(
        self,
        intervals: list[tuple[float, float]],
        merge_gap: float,
    ) -> list[tuple[float, float]]:
        if not intervals:
            return []
        ordered = sorted(intervals, key=lambda x: x[0])
        merged: list[tuple[float, float]] = [ordered[0]]
        for start, end in ordered[1:]:
            last_start, last_end = merged[-1]
            if start - last_end <= merge_gap:
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))
        return merged

    def _reduce_intervals(
        self,
        intervals: list[tuple[float, float]],
        max_segments: int,
    ) -> list[tuple[float, float]]:
        merged = intervals[:]
        while len(merged) > max_segments:
            best_i = 0
            best_gap = float("inf")
            for i in range(len(merged) - 1):
                gap = merged[i + 1][0] - merged[i][1]
                if gap < best_gap:
                    best_gap = gap
                    best_i = i
            left = merged[best_i]
            right = merged[best_i + 1]
            merged[best_i : best_i + 2] = [(left[0], right[1])]
        return merged
