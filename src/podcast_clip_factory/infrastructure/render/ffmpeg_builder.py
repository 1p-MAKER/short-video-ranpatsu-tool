from __future__ import annotations

from pathlib import Path

from podcast_clip_factory.domain.models import ClipCandidate, ImpactOverlayStyle, TitleOverlayStyle
from podcast_clip_factory.infrastructure.render.letterbox_layout import build_filtergraph
from podcast_clip_factory.utils.config import RenderConfig


class FFmpegCommandBuilder:
    def __init__(self, config: RenderConfig) -> None:
        self.config = config

    def build(
        self,
        input_video: Path,
        output_video: Path,
        subtitle_path: Path | None,
        candidate: ClipCandidate,
        title_style: TitleOverlayStyle | None = None,
        impact_style: ImpactOverlayStyle | None = None,
        fallback_software_codec: bool = False,
    ) -> list[str]:
        codec = "libx264" if fallback_software_codec else self.config.video_codec
        style = title_style or TitleOverlayStyle()
        lower_style = impact_style or ImpactOverlayStyle()
        filter_graph = build_filtergraph(
            subtitle_path=str(subtitle_path) if subtitle_path else None,
            title_text=candidate.title,
            impact_text=(candidate.punchline or ""),
            video_width=self.config.video_width,
            video_height=self.config.video_height,
            center_width=self.config.center_width,
            center_height=self.config.center_height,
            blur_sigma=self.config.background_blur_sigma,
            font_name=style.font_name,
            font_size=style.font_size,
            title_y=style.y,
            text_background=style.background,
            text_background_opacity=style.background_opacity,
            text_background_padding=style.background_padding,
            impact_font_name=lower_style.font_name,
            impact_font_size=lower_style.font_size,
            impact_y=lower_style.y,
            impact_background=lower_style.background,
            impact_background_opacity=lower_style.background_opacity,
            impact_background_padding=lower_style.background_padding,
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
