from __future__ import annotations

import tempfile
from pathlib import Path

from podcast_clip_factory.infrastructure.transcriber.mlx_whisper import MLXWhisperTranscriber


class _Proc:
    def __init__(self, code: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = code
        self.stdout = stdout
        self.stderr = stderr


def _dummy_named_tmp(path: Path):
    class _Tmp:
        def __enter__(self):
            path.touch()
            self.name = str(path)
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    return _Tmp()


def test_mlx_transcriber_subprocess_failure(monkeypatch, tmp_path: Path):
    out = tmp_path / "mlx_out_fail.json"

    monkeypatch.setattr(
        tempfile,
        "NamedTemporaryFile",
        lambda suffix, delete: _dummy_named_tmp(out),
    )

    def fake_run(*args, **kwargs):
        return _Proc(-6, stderr="Abort trap")

    monkeypatch.setattr("podcast_clip_factory.infrastructure.transcriber.mlx_whisper.subprocess.run", fake_run)

    transcriber = MLXWhisperTranscriber(model="dummy")
    try:
        transcriber._run_mlx_in_subprocess(tmp_path / "dummy.wav")
        assert False, "Expected RuntimeError"
    except RuntimeError as exc:
        assert "code=-6" in str(exc)


def test_mlx_transcriber_subprocess_success(monkeypatch, tmp_path: Path):
    out = tmp_path / "mlx_out_ok.json"

    monkeypatch.setattr(
        tempfile,
        "NamedTemporaryFile",
        lambda suffix, delete: _dummy_named_tmp(out),
    )

    def fake_run(cmd, capture_output, text):
        Path(cmd[6]).write_text(
            '{"segments": [], "language": "ja", "duration": 0.0}',
            encoding="utf-8",
        )
        return _Proc(0)

    monkeypatch.setattr("podcast_clip_factory.infrastructure.transcriber.mlx_whisper.subprocess.run", fake_run)

    transcriber = MLXWhisperTranscriber(model="dummy")
    payload = transcriber._run_mlx_in_subprocess(tmp_path / "dummy.wav")
    assert payload["language"] == "ja"
