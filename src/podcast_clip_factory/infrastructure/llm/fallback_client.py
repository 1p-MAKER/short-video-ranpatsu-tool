from __future__ import annotations

from podcast_clip_factory.domain.models import ClipCandidate, MediaInfo, Transcript


class HeuristicClipAnalyzer:
    """Deterministic fallback when cloud LLM is unavailable."""

    def select_clips(
        self,
        transcript: Transcript,
        media_info: MediaInfo,
        target_count: int,
        min_sec: int,
        max_sec: int,
    ) -> list[ClipCandidate]:
        segments = transcript.segments
        if not segments:
            return []

        total = transcript.duration_sec or media_info.duration_sec or segments[-1].end
        if total <= 0:
            return []

        window = float(max_sec)
        step = max(float(min_sec), total / max(target_count, 1))
        candidates: list[ClipCandidate] = []
        cursor = 0.0
        idx = 1

        while len(candidates) < target_count and cursor + min_sec <= total:
            start = cursor
            end = min(total, start + window)
            text = self._collect_text(segments, start, end)
            if not text:
                cursor += step
                continue

            title = text[:28].replace("\n", " ").strip() or f"切り抜き {idx}"
            candidates.append(
                ClipCandidate(
                    clip_id=f"heuristic_{idx:02d}",
                    start_sec=start,
                    end_sec=end,
                    title=title,
                    hook=text[:100],
                    reason="クラウドAPI未使用時のヒューリスティック抽出",
                    score=max(0.2, 0.8 - idx * 0.03),
                )
            )
            idx += 1
            cursor += step

        return candidates

    def _collect_text(self, segments, start: float, end: float) -> str:
        return " ".join(seg.text for seg in segments if seg.start < end and seg.end > start).strip()
