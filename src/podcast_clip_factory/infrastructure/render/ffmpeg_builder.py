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
        speech_intervals: list[tuple[float, float]] | None = None,
        fallback_software_codec: bool = False,
    ) -> list[str]:
        codec = "libx264" if fallback_software_codec else self.config.video_codec
        style = title_style or TitleOverlayStyle()
        lower_style = impact_style or ImpactOverlayStyle()
        use_compaction = bool(speech_intervals)
        filter_graph = self._build_filter_graph(
            subtitle_path=subtitle_path,
            title_text=candidate.title,
            impact_text=(candidate.punchline or ""),
            title_style=style,
            impact_style=lower_style,
            speech_intervals=speech_intervals or [],
        )

        audio_map = "[srca]" if use_compaction else "0:a:0?"

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
            audio_map,
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

    def _build_filter_graph(
        self,
        subtitle_path: Path | None,
        title_text: str,
        impact_text: str,
        title_style: TitleOverlayStyle,
        impact_style: ImpactOverlayStyle,
        speech_intervals: list[tuple[float, float]],
    ) -> str:
        if speech_intervals:
            trim_parts: list[str] = []
            concat_inputs: list[str] = []
            for i, (start, end) in enumerate(speech_intervals):
                trim_parts.append(
                    f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS[sv{i}]"
                )
                trim_parts.append(
                    f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[sa{i}]"
                )
                concat_inputs.append(f"[sv{i}][sa{i}]")

            concat_graph = (
                ";".join(trim_parts)
                + ";"
                + "".join(concat_inputs)
                + f"concat=n={len(speech_intervals)}:v=1:a=1[srcv][srca]"
            )
            layout_graph = build_filtergraph(
                subtitle_path=str(subtitle_path) if subtitle_path else None,
                title_text=title_text,
                impact_text=impact_text,
                video_width=self.config.video_width,
                video_height=self.config.video_height,
                center_width=self.config.center_width,
                center_height=self.config.center_height,
                blur_sigma=self.config.background_blur_sigma,
                font_name=title_style.font_name,
                font_size=title_style.font_size,
                title_y=title_style.y,
                text_background=title_style.background,
                text_background_opacity=title_style.background_opacity,
                text_background_padding=title_style.background_padding,
                impact_font_name=impact_style.font_name,
                impact_font_size=impact_style.font_size,
                impact_y=impact_style.y,
                impact_background=impact_style.background,
                impact_background_opacity=impact_style.background_opacity,
                impact_background_padding=impact_style.background_padding,
                video_input_label="srcv",
            )
            return f"{concat_graph};{layout_graph}"

        return build_filtergraph(
            subtitle_path=str(subtitle_path) if subtitle_path else None,
            title_text=title_text,
            impact_text=impact_text,
            video_width=self.config.video_width,
            video_height=self.config.video_height,
            center_width=self.config.center_width,
            center_height=self.config.center_height,
            blur_sigma=self.config.background_blur_sigma,
            font_name=title_style.font_name,
            font_size=title_style.font_size,
            title_y=title_style.y,
            text_background=title_style.background,
            text_background_opacity=title_style.background_opacity,
            text_background_padding=title_style.background_padding,
            impact_font_name=impact_style.font_name,
            impact_font_size=impact_style.font_size,
            impact_y=impact_style.y,
            impact_background=impact_style.background,
            impact_background_opacity=impact_style.background_opacity,
            impact_background_padding=impact_style.background_padding,
        )
