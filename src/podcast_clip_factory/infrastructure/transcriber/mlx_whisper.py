from __future__ import annotations

from pathlib import Path

from podcast_clip_factory.domain.models import Transcript, TranscriptSegment, WordToken


class MLXWhisperTranscriber:
    def __init__(self, model: str, word_timestamps: bool = True) -> None:
        self.model = model
        self.word_timestamps = word_timestamps

    def transcribe(self, audio_path: Path) -> Transcript:
        try:
            from mlx_whisper import transcribe
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("mlx-whisper is not installed") from exc

        result = transcribe(
            str(audio_path),
            path_or_hf_repo=self.model,
            word_timestamps=self.word_timestamps,
        )

        segments: list[TranscriptSegment] = []
        for seg in result.get("segments", []):
            words: list[WordToken] = []
            for word in seg.get("words", []):
                words.append(
                    WordToken(
                        word=str(word.get("word", "")).strip(),
                        start=float(word.get("start", seg.get("start", 0.0))),
                        end=float(word.get("end", seg.get("end", 0.0))),
                    )
                )
            segments.append(
                TranscriptSegment(
                    start=float(seg.get("start", 0.0)),
                    end=float(seg.get("end", 0.0)),
                    text=str(seg.get("text", "")).strip(),
                    words=words,
                )
            )

        return Transcript(
            segments=segments,
            language=str(result.get("language", "ja")),
            duration_sec=float(result.get("duration", 0.0)) if result.get("duration") else 0.0,
        )
