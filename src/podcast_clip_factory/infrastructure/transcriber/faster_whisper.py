from __future__ import annotations

from pathlib import Path

from podcast_clip_factory.domain.models import Transcript, TranscriptSegment, WordToken


class FasterWhisperTranscriber:
    def __init__(self, model: str, word_timestamps: bool = True) -> None:
        self.model_name = model
        self.word_timestamps = word_timestamps
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("faster-whisper is not installed") from exc
            self._model = WhisperModel(self.model_name, device="cpu", compute_type="int8")
        return self._model

    def transcribe(self, audio_path: Path, cancel_event=None) -> Transcript:
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError("transcription cancelled")

        model = self._get_model()
        segments_iter, info = model.transcribe(
            str(audio_path),
            word_timestamps=self.word_timestamps,
            vad_filter=True,
        )

        segments: list[TranscriptSegment] = []
        for seg in segments_iter:
            if cancel_event is not None and cancel_event.is_set():
                raise RuntimeError("transcription cancelled")
            words: list[WordToken] = []
            for word in getattr(seg, "words", []) or []:
                words.append(WordToken(word=word.word.strip(), start=float(word.start), end=float(word.end)))
            segments.append(
                TranscriptSegment(
                    start=float(seg.start),
                    end=float(seg.end),
                    text=seg.text.strip(),
                    words=words,
                )
            )

        return Transcript(
            segments=segments,
            language=getattr(info, "language", "ja") or "ja",
            duration_sec=segments[-1].end if segments else 0.0,
        )
