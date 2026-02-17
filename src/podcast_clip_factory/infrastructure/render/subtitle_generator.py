from __future__ import annotations

from pathlib import Path

from podcast_clip_factory.domain.models import ClipCandidate, Transcript
from podcast_clip_factory.utils.config import SubtitleConfig


class SubtitleGenerator:
    def __init__(self, config: SubtitleConfig) -> None:
        self.config = config

    def generate(
        self,
        path: Path,
        candidate: ClipCandidate,
        transcript: Transcript,
        speech_intervals: list[tuple[float, float]] | None = None,
    ) -> Path:
        lines = self._build_dialogue_lines(candidate, transcript, speech_intervals=speech_intervals)
        content = self._render_ass(lines)
        path.write_text(content, encoding="utf-8")
        return path

    def _build_dialogue_lines(
        self,
        candidate: ClipCandidate,
        transcript: Transcript,
        speech_intervals: list[tuple[float, float]] | None = None,
    ) -> list[tuple[float, float, str]]:
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
            if speech_intervals:
                mapped = self._map_to_compacted_timeline(rel_start, rel_end, speech_intervals)
                for mapped_start, mapped_end in mapped:
                    if mapped_end > mapped_start:
                        lines.append((mapped_start, mapped_end, text))
            else:
                lines.append((rel_start, rel_end, text))

        return lines

    def _map_to_compacted_timeline(
        self,
        seg_start: float,
        seg_end: float,
        speech_intervals: list[tuple[float, float]],
    ) -> list[tuple[float, float]]:
        mapped: list[tuple[float, float]] = []
        out_cursor = 0.0
        for keep_start, keep_end in speech_intervals:
            if keep_end <= keep_start:
                continue
            overlap_start = max(seg_start, keep_start)
            overlap_end = min(seg_end, keep_end)
            if overlap_end > overlap_start:
                mapped_start = out_cursor + (overlap_start - keep_start)
                mapped_end = out_cursor + (overlap_end - keep_start)
                mapped.append((mapped_start, mapped_end))
            out_cursor += keep_end - keep_start
        return mapped

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
