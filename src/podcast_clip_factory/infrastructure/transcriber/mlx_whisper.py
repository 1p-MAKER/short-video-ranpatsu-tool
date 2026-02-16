from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from podcast_clip_factory.domain.models import Transcript, TranscriptSegment, WordToken


class MLXWhisperTranscriber:
    def __init__(self, model: str, word_timestamps: bool = True) -> None:
        self.model = model
        self.word_timestamps = word_timestamps

    def transcribe(self, audio_path: Path) -> Transcript:
        result = self._run_mlx_in_subprocess(audio_path)

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

    def _run_mlx_in_subprocess(self, audio_path: Path) -> dict:
        script = (
            "import json, sys\n"
            "from mlx_whisper import transcribe\n"
            "audio_path = sys.argv[1]\n"
            "model = sys.argv[2]\n"
            "word_ts = sys.argv[3] == '1'\n"
            "out_path = sys.argv[4]\n"
            "result = transcribe(audio_path, path_or_hf_repo=model, word_timestamps=word_ts)\n"
            "with open(out_path, 'w', encoding='utf-8') as f:\n"
            "    json.dump(result, f, ensure_ascii=False)\n"
        )

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        cmd = [
            sys.executable,
            "-c",
            script,
            str(audio_path),
            self.model,
            "1" if self.word_timestamps else "0",
            str(tmp_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        try:
            if proc.returncode != 0:
                stderr = proc.stderr.strip() or proc.stdout.strip() or "unknown mlx-whisper failure"
                raise RuntimeError(
                    f"mlx-whisper subprocess failed (code={proc.returncode}): {stderr}"
                )
            return json.loads(tmp_path.read_text(encoding="utf-8"))
        finally:
            tmp_path.unlink(missing_ok=True)
