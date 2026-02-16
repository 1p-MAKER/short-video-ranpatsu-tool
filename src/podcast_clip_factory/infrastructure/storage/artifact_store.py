from __future__ import annotations

import json
from pathlib import Path

from podcast_clip_factory.domain.models import Transcript, TranscriptSegment, WordToken


class ArtifactStore:
    def __init__(self, runs_root: Path) -> None:
        self.runs_root = runs_root
        self.runs_root.mkdir(parents=True, exist_ok=True)

    def job_dir(self, job_id: str) -> Path:
        path = self.runs_root / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def audio_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "audio.wav"

    def transcript_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "transcript_full.json"

    def metadata_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "metadata.json"

    def final_metadata_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "final_metadata.json"

    def output_dir(self, job_id: str) -> Path:
        path = self.job_dir(job_id) / "output"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def final_dir(self, job_id: str) -> Path:
        path = self.job_dir(job_id) / "final"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_json(self, path: Path, payload: dict | list) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def save_transcript(self, job_id: str, transcript: Transcript) -> Path:
        payload = {
            "language": transcript.language,
            "duration_sec": transcript.duration_sec,
            "segments": [
                {
                    "start": s.start,
                    "end": s.end,
                    "text": s.text,
                    "words": [{"word": w.word, "start": w.start, "end": w.end} for w in s.words],
                }
                for s in transcript.segments
            ],
        }
        path = self.transcript_path(job_id)
        self.write_json(path, payload)
        return path

    def load_transcript(self, path: Path) -> Transcript:
        payload = json.loads(path.read_text(encoding="utf-8"))
        segments = [
            TranscriptSegment(
                start=float(seg["start"]),
                end=float(seg["end"]),
                text=str(seg["text"]),
                words=[
                    WordToken(word=str(w["word"]), start=float(w["start"]), end=float(w["end"]))
                    for w in seg.get("words", [])
                ],
            )
            for seg in payload.get("segments", [])
        ]
        return Transcript(
            segments=segments,
            language=str(payload.get("language", "ja")),
            duration_sec=float(payload.get("duration_sec", 0.0)),
        )
