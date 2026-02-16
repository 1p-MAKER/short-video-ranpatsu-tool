from __future__ import annotations

from pathlib import Path

from podcast_clip_factory.domain.models import ClipCandidate, Transcript
from podcast_clip_factory.utils.config import SubtitleConfig


class SubtitleGenerator:
    def __init__(self, config: SubtitleConfig) -> None:
        self.config = config

    def generate(self, path: Path, candidate: ClipCandidate, transcript: Transcript) -> Path:
        lines = self._build_dialogue_lines(candidate, transcript)
        content = self._render_ass(lines)
        path.write_text(content, encoding="utf-8")
        return path

    def _build_dialogue_lines(self, candidate: ClipCandidate, transcript: Transcript) -> list[tuple[float, float, str]]:
        start = candidate.start_sec
        end = candidate.end_sec
        lines: list[tuple[float, float, str]] = []

        for seg in transcript.segments:
            if seg.end <= start or seg.start >= end:
                continue
            rel_start = max(0.0, seg.start - start)
            rel_end = min(end - start, seg.end - start)
            if rel_end <= rel_start:
                continue
            text = self._sanitize_text(seg.text)
            lines.append((rel_start, rel_end, text))

        return lines

    def _render_ass(self, lines: list[tuple[float, float, str]]) -> str:
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{self.config.font_name},{self.config.font_size},{self.config.primary_color},{self.config.highlight_color},{self.config.outline_color},&H64000000,0,0,0,0,100,100,0,0,1,3,0,2,40,40,{self.config.bottom_margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        body = "\n".join(
            f"Dialogue: 0,{self._fmt_time(start)},{self._fmt_time(end)},Default,,0,0,0,,{text}"
            for start, end, text in lines
        )
        return header + body + "\n"

    def _fmt_time(self, sec: float) -> str:
        hours = int(sec // 3600)
        mins = int((sec % 3600) // 60)
        secs = int(sec % 60)
        centi = int(round((sec - int(sec)) * 100))
        return f"{hours}:{mins:02d}:{secs:02d}.{centi:02d}"

    def _sanitize_text(self, text: str) -> str:
        return text.replace("{", "(").replace("}", ")").replace("\n", " ").strip()
