from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AppConfig:
    target_clips: int
    min_clips: int
    clip_min_sec: int
    clip_max_sec: int
    title_max_chars: int
    render_parallelism: int
    manual_start_only: bool
    max_render_retries: int
    default_media_dir: str = "/Volumes/1peiHDD_2TB/DaVinciResolve_material_HDD/RADIO"
    enable_silence_compaction: bool = True
    silence_speech_pad_sec: float = 0.12
    silence_merge_gap_sec: float = 0.25
    silence_min_segment_sec: float = 0.18
    silence_min_cut_total_sec: float = 0.8
    silence_max_segments: int = 24
    silence_detect_noise_db: float = -35.0
    silence_detect_min_sec: float = 0.35


@dataclass(slots=True)
class TranscribeConfig:
    primary: str
    fallback: str
    word_timestamps: bool
    mlx_model: str
    faster_model: str


@dataclass(slots=True)
class LLMConfig:
    primary: str
    fallback: str
    require_cloud: bool
    max_retries: int
    json_repair: bool
    gemini_model: str
    gemini_api_key: str
    openai_api_key: str


@dataclass(slots=True)
class RenderConfig:
    video_width: int
    video_height: int
    center_width: int
    center_height: int
    background_blur_sigma: int
    video_codec: str
    audio_codec: str
    audio_bitrate: str


@dataclass(slots=True)
class SubtitleConfig:
    enable_subtitles: bool
    font_name: str
    font_size: int
    highlight_color: str
    primary_color: str
    outline_color: str
    bottom_margin: int


@dataclass(slots=True)
class Settings:
    app: AppConfig
    transcribe: TranscribeConfig
    llm: LLMConfig
    render: RenderConfig
    subtitle: SubtitleConfig
    root_dir: Path


def load_settings(root_dir: Path) -> Settings:
    config_path = root_dir / "config" / "default.toml"
    with config_path.open("rb") as fh:
        raw = tomllib.load(fh)

    app = raw["app"]
    trans = raw["transcribe"]
    llm = raw["llm"]
    render = raw["render"]
    subtitle = raw["subtitle"]

    return Settings(
        app=AppConfig(
            target_clips=int(app["target_clips"]),
            min_clips=int(app["min_clips"]),
            clip_min_sec=int(app["clip_min_sec"]),
            clip_max_sec=int(app["clip_max_sec"]),
            title_max_chars=int(app["title_max_chars"]),
            render_parallelism=max(1, int(app["render_parallelism"])),
            manual_start_only=bool(app["manual_start_only"]),
            max_render_retries=int(app["max_render_retries"]),
            default_media_dir=str(
                app.get("default_media_dir", "/Volumes/1peiHDD_2TB/DaVinciResolve_material_HDD/RADIO")
            ),
            enable_silence_compaction=bool(app.get("enable_silence_compaction", True)),
            silence_speech_pad_sec=float(app.get("silence_speech_pad_sec", 0.12)),
            silence_merge_gap_sec=float(app.get("silence_merge_gap_sec", 0.25)),
            silence_min_segment_sec=float(app.get("silence_min_segment_sec", 0.18)),
            silence_min_cut_total_sec=float(app.get("silence_min_cut_total_sec", 0.8)),
            silence_max_segments=max(1, int(app.get("silence_max_segments", 24))),
            silence_detect_noise_db=float(app.get("silence_detect_noise_db", -35.0)),
            silence_detect_min_sec=float(app.get("silence_detect_min_sec", 0.35)),
        ),
        transcribe=TranscribeConfig(
            primary=str(trans["primary"]),
            fallback=str(trans["fallback"]),
            word_timestamps=bool(trans["word_timestamps"]),
            mlx_model=os.getenv("MLX_WHISPER_MODEL", "mlx-community/whisper-large-v3-turbo"),
            faster_model=os.getenv("FASTER_WHISPER_MODEL", "small"),
        ),
        llm=LLMConfig(
            primary=str(llm["primary"]),
            fallback=str(llm["fallback"]),
            require_cloud=bool(llm.get("require_cloud", True)),
            max_retries=int(llm["max_retries"]),
            json_repair=bool(llm["json_repair"]),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        ),
        render=RenderConfig(
            video_width=int(render["video_width"]),
            video_height=int(render["video_height"]),
            center_width=int(render["center_width"]),
            center_height=int(render["center_height"]),
            background_blur_sigma=int(render["background_blur_sigma"]),
            video_codec=str(render["video_codec"]),
            audio_codec=str(render["audio_codec"]),
            audio_bitrate=str(render["audio_bitrate"]),
        ),
        subtitle=SubtitleConfig(
            enable_subtitles=bool(subtitle.get("enable_subtitles", False)),
            font_name=str(subtitle["font_name"]),
            font_size=int(subtitle["font_size"]),
            highlight_color=str(subtitle["highlight_color"]),
            primary_color=str(subtitle["primary_color"]),
            outline_color=str(subtitle["outline_color"]),
            bottom_margin=int(subtitle["bottom_margin"]),
        ),
        root_dir=root_dir,
    )
