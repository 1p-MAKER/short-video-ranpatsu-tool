from __future__ import annotations

import json
import subprocess
from pathlib import Path

from podcast_clip_factory.domain.models import MediaInfo


class CommandError(RuntimeError):
    pass


def run_command(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise CommandError(f"Command failed: {' '.join(cmd)}\n{proc.stderr}")


def ffprobe_media(input_path: Path) -> MediaInfo:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(input_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise CommandError(proc.stderr)

    payload = json.loads(proc.stdout)
    stream = payload["streams"][0]
    duration_sec = float(payload["format"].get("duration", 0.0))
    frame_rate = stream.get("r_frame_rate", "30/1")
    num, den = frame_rate.split("/")
    fps = float(num) / float(den)
    return MediaInfo(
        duration_sec=duration_sec,
        width=int(stream["width"]),
        height=int(stream["height"]),
        fps=fps,
    )


def extract_audio(input_video: Path, output_wav: Path) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_video),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ac",
        "1",
        "-ar",
        "16000",
        str(output_wav),
    ]
    run_command(cmd)
