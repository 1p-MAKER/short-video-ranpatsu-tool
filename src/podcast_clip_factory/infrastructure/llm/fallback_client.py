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
        total = transcript.duration_sec or media_info.duration_sec
        if total <= 0 and segments:
            total = segments[-1].end
        if total <= 0:
            return []
        if not segments:
            return self._fallback_without_transcript(total, target_count, min_sec, max_sec)

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

    def _fallback_without_transcript(
        self,
        total_duration: float,
        target_count: int,
        min_sec: int,
        max_sec: int,
    ) -> list[ClipCandidate]:
        candidates: list[ClipCandidate] = []
        window = float(max_sec)
        step = max(float(min_sec), total_duration / max(target_count, 1))
        cursor = 0.0
        idx = 1

        while len(candidates) < target_count and cursor + min_sec <= total_duration:
            start = cursor
            end = min(total_duration, start + window)
            if end - start < min_sec:
                break
            candidates.append(
                ClipCandidate(
                    clip_id=f"heuristic_{idx:02d}",
                    start_sec=start,
                    end_sec=end,
                    title=f"切り抜き {idx}",
                    hook="文字起こしが空のため時間窓で抽出",
                    reason="文字起こし空のフォールバック抽出",
                    score=max(0.15, 0.6 - idx * 0.03),
                )
            )
            idx += 1
            cursor += step

        return candidates

    def _collect_text(self, segments, start: float, end: float) -> str:
        return " ".join(seg.text for seg in segments if seg.start < end and seg.end > start).strip()
