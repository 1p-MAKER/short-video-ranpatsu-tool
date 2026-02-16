from __future__ import annotations

import math
from dataclasses import dataclass

from .models import ClipCandidate, Transcript, TranscriptSegment


@dataclass(slots=True)
class ClipRuleConfig:
    target_clips: int
    min_clips: int
    min_sec: int
    max_sec: int
    title_max_chars: int
    overlap_tolerance_sec: float = 3.0


class ClipRuleEngine:
    def __init__(self, config: ClipRuleConfig) -> None:
        self.config = config

    def finalize(self, candidates: list[ClipCandidate], transcript: Transcript) -> list[ClipCandidate]:
        normalized = [self._normalize_duration(c, transcript.duration_sec) for c in candidates]
        deduped = self._remove_overlaps(normalized)
        capped = [self._cap_title(c) for c in deduped]

        if len(capped) < self.config.min_clips:
            capped = self._fill_shortage(capped, transcript)

        capped.sort(key=lambda c: c.score, reverse=True)
        return capped[: self.config.target_clips]

    def _normalize_duration(self, candidate: ClipCandidate, total_duration: float) -> ClipCandidate:
        start = max(0.0, candidate.start_sec)
        end = min(total_duration, candidate.end_sec) if total_duration > 0 else candidate.end_sec
        duration = max(0.0, end - start)

        if duration > self.config.max_sec:
            end = start + self.config.max_sec
        elif duration < self.config.min_sec:
            end = min(total_duration or (start + self.config.min_sec), start + self.config.min_sec)

        if end <= start:
            end = start + self.config.min_sec

        return ClipCandidate(
            clip_id=candidate.clip_id,
            start_sec=start,
            end_sec=end,
            title=candidate.title,
            hook=candidate.hook,
            reason=candidate.reason,
            score=candidate.score,
            punchline=candidate.punchline,
        )

    def _cap_title(self, candidate: ClipCandidate) -> ClipCandidate:
        title = candidate.title.strip()
        if len(title) > self.config.title_max_chars:
            title = title[: self.config.title_max_chars].rstrip()
        return ClipCandidate(
            clip_id=candidate.clip_id,
            start_sec=candidate.start_sec,
            end_sec=candidate.end_sec,
            title=title,
            hook=candidate.hook,
            reason=candidate.reason,
            score=candidate.score,
            punchline=candidate.punchline,
        )

    def _remove_overlaps(self, candidates: list[ClipCandidate]) -> list[ClipCandidate]:
        ordered = sorted(candidates, key=lambda c: (c.start_sec, -c.score))
        result: list[ClipCandidate] = []
        for candidate in ordered:
            if not any(self._overlap(existing, candidate) for existing in result):
                result.append(candidate)
        return result

    def _overlap(self, left: ClipCandidate, right: ClipCandidate) -> bool:
        overlap = min(left.end_sec, right.end_sec) - max(left.start_sec, right.start_sec)
        return overlap > self.config.overlap_tolerance_sec

    def _fill_shortage(self, current: list[ClipCandidate], transcript: Transcript) -> list[ClipCandidate]:
        used = {(round(c.start_sec, 1), round(c.end_sec, 1)) for c in current}
        filler = self._build_filler_candidates(transcript, offset=len(current))
        for candidate in filler:
            key = (round(candidate.start_sec, 1), round(candidate.end_sec, 1))
            if key in used:
                continue
            if any(self._overlap(existing, candidate) for existing in current):
                continue
            current.append(candidate)
            used.add(key)
            if len(current) >= self.config.min_clips:
                break
        return current

    def _build_filler_candidates(self, transcript: Transcript, offset: int) -> list[ClipCandidate]:
        if not transcript.segments:
            return []

        segs = transcript.segments
        total = transcript.duration_sec or segs[-1].end
        step = max(self.config.min_sec, math.floor(self.config.max_sec * 0.8))
        candidates: list[ClipCandidate] = []
        cursor = 0.0
        idx = 1
        while cursor + self.config.min_sec <= total:
            start = cursor
            end = min(total, start + self.config.max_sec)
            if end - start < self.config.min_sec:
                break
            text = self._collect_text(segs, start, end)
            title_seed = text[: self.config.title_max_chars] or f"切り抜き {idx}"
            candidates.append(
                ClipCandidate(
                    clip_id=f"filler_{offset + idx:02d}",
                    start_sec=start,
                    end_sec=end,
                    title=title_seed,
                    hook=text[:120],
                    reason="候補不足のためルール補完",
                    score=0.35,
                )
            )
            cursor += step
            idx += 1
        return candidates

    def _collect_text(self, segments: list[TranscriptSegment], start: float, end: float) -> str:
        return " ".join(s.text.strip() for s in segments if s.start < end and s.end > start).strip()
