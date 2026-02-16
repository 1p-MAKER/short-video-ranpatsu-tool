from __future__ import annotations

from pathlib import Path

from podcast_clip_factory.domain.models import ClipCandidate
from podcast_clip_factory.infrastructure.render.letterbox_layout import build_filtergraph
from podcast_clip_factory.utils.config import RenderConfig


class FFmpegCommandBuilder:
    def __init__(self, config: RenderConfig) -> None:
        self.config = config

    def build(
        self,
        input_video: Path,
        output_video: Path,
        subtitle_path: Path,
        candidate: ClipCandidate,
        fallback_software_codec: bool = False,
    ) -> list[str]:
        codec = "libx264" if fallback_software_codec else self.config.video_codec
        filter_graph = build_filtergraph(
            subtitle_path=str(subtitle_path),
            title_text=candidate.title,
            video_width=self.config.video_width,
            video_height=self.config.video_height,
            center_width=self.config.center_width,
            center_height=self.config.center_height,
            blur_sigma=self.config.background_blur_sigma,
        )

        return [
            "ffmpeg",
            "-y",
            "-ss",
            f"{candidate.start_sec:.3f}",
            "-to",
            f"{candidate.end_sec:.3f}",
            "-i",
            str(input_video),
            "-filter_complex",
            filter_graph,
            "-map",
            "[v]",
            "-map",
            "0:a:0?",
            "-c:v",
            codec,
            "-c:a",
            self.config.audio_codec,
            "-b:a",
            self.config.audio_bitrate,
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output_video),
        ]
