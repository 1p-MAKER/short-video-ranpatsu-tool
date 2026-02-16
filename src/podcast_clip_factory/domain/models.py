from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path


class JobStatus(StrEnum):
    QUEUED = "queued"
    PREPROCESSING = "preprocessing"
    TRANSCRIBING = "transcribing"
    SELECTING = "selecting"
    PREPARING = "preparing"
    RENDERING = "rendering"
    REVIEW_PENDING = "review_pending"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class WordToken:
    word: str
    start: float
    end: float


@dataclass(slots=True)
class TranscriptSegment:
    start: float
    end: float
    text: str
    words: list[WordToken] = field(default_factory=list)


@dataclass(slots=True)
class Transcript:
    segments: list[TranscriptSegment]
    language: str = "ja"
    duration_sec: float = 0.0

    @property
    def full_text(self) -> str:
        return "\n".join(s.text.strip() for s in self.segments if s.text.strip())


@dataclass(slots=True)
class ClipCandidate:
    clip_id: str
    start_sec: float
    end_sec: float
    title: str
    hook: str
    reason: str
    score: float
    punchline: str = ""

    @property
    def duration(self) -> float:
        return max(0.0, self.end_sec - self.start_sec)


@dataclass(slots=True)
class RenderedClip:
    clip_id: str
    title: str
    start_sec: float
    end_sec: float
    video_path: Path
    subtitle_path: Path


@dataclass(slots=True)
class ReviewDecision:
    clip_id: str
    selected: bool
    edited_title: str


@dataclass(slots=True)
class MediaInfo:
    duration_sec: float
    width: int
    height: int
    fps: float


@dataclass(slots=True)
class JobRecord:
    job_id: str
    input_path: Path
    status: JobStatus
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error_message: str = ""


@dataclass(slots=True)
class PipelineResult:
    job: JobRecord
    media_info: MediaInfo
    transcript: Transcript
    rendered_clips: list[RenderedClip]
    candidates: list[ClipCandidate]
