from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from podcast_clip_factory.domain.models import ClipCandidate, MediaInfo, Transcript


class GeminiClipAnalyzer:
    def __init__(self, api_key: str, model: str, prompt_path: Path) -> None:
        self.api_key = api_key
        self.model = model
        self.prompt_path = prompt_path

    def select_clips(
        self,
        transcript: Transcript,
        media_info: MediaInfo,
        target_count: int,
        min_sec: int,
        max_sec: int,
    ) -> list[ClipCandidate]:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is empty")

        system_prompt = self.prompt_path.read_text(encoding="utf-8")
        user_prompt = self._build_user_prompt(transcript, media_info, target_count, min_sec, max_sec)
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2,
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as res:
                body = res.read().decode("utf-8")
        except urllib.error.URLError as exc:  # pragma: no cover
            raise RuntimeError(f"Gemini request failed: {exc}") from exc

        response_json = json.loads(body)
        text = (
            response_json.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        if not text:
            raise RuntimeError("Gemini response body was empty")

        raw_candidates = json.loads(text)
        candidates: list[ClipCandidate] = []
        for idx, item in enumerate(raw_candidates, start=1):
            candidates.append(
                ClipCandidate(
                    clip_id=str(item.get("clip_id") or f"llm_{idx:02d}"),
                    start_sec=float(item["start_sec"]),
                    end_sec=float(item["end_sec"]),
                    title=str(item.get("title") or f"切り抜き {idx}"),
                    hook=str(item.get("hook") or ""),
                    reason=str(item.get("reason") or ""),
                    score=float(item.get("score", 0.5)),
                    punchline=str(item.get("punchline") or ""),
                )
            )
        return candidates

    def _build_user_prompt(
        self,
        transcript: Transcript,
        media_info: MediaInfo,
        target_count: int,
        min_sec: int,
        max_sec: int,
    ) -> str:
        return (
            f"target_count={target_count}, min_sec={min_sec}, max_sec={max_sec}, "
            f"duration_sec={media_info.duration_sec}\n\n"
            "Transcript:\n"
            f"{transcript.full_text}"
        )
