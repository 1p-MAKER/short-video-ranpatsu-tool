from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .models import ClipCandidate, MediaInfo, RenderedClip, Transcript


class Transcriber(Protocol):
    def transcribe(self, audio_path: Path) -> Transcript:
        """Return transcript with word-level timestamps."""


class ClipAnalyzer(Protocol):
    def select_clips(
        self,
        transcript: Transcript,
        media_info: MediaInfo,
        target_count: int,
        min_sec: int,
        max_sec: int,
    ) -> list[ClipCandidate]:
        """Return ranked clip candidates."""


class Renderer(Protocol):
    def render(
        self,
        input_video: Path,
        output_dir: Path,
        candidates: list[ClipCandidate],
        transcript: Transcript,
    ) -> list[RenderedClip]:
        """Render clips and return output metadata."""
