from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from podcast_clip_factory.domain.models import ClipCandidate, MediaInfo, Transcript


class GeminiClipAnalyzer:
    def __init__(self, api_key: str, model: str, prompt_path: Path, json_repair: bool = True) -> None:
        self.api_key = api_key.strip()
        self.model = model
        self.prompt_path = prompt_path
        self.json_repair = json_repair
        self.ssl_context = self._build_ssl_context()

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

        response_json = self._request_json(url=url, payload=payload)
        return self._parse_candidates(response_json)

    def check_availability(self) -> None:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is empty")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": "ping"}]}],
            "generationConfig": {"responseMimeType": "text/plain", "temperature": 0.0},
        }
        self._request_json(url=url, payload=payload, timeout_sec=20)

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

    def _request_json(self, url: str, payload: dict[str, Any], timeout_sec: int = 90) -> dict[str, Any]:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec, context=self.ssl_context) as res:
                body = res.read().decode("utf-8")
        except urllib.error.HTTPError as exc:  # pragma: no cover
            detail = ""
            try:
                error_body = exc.read().decode("utf-8")
                parsed = json.loads(error_body)
                message = parsed.get("error", {}).get("message")
                detail = message or error_body
            except Exception:
                detail = str(exc)
            raise RuntimeError(f"Gemini HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover
            raise RuntimeError(f"Gemini request failed: {exc}") from exc

        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Gemini response was not valid JSON") from exc

    def _parse_candidates(self, response_json: dict[str, Any]) -> list[ClipCandidate]:
        text = self._extract_text(response_json)
        if not text:
            prompt_feedback = response_json.get("promptFeedback", {})
            block_reason = prompt_feedback.get("blockReason")
            finish_reason = (
                response_json.get("candidates", [{}])[0].get("finishReason")
                if response_json.get("candidates")
                else ""
            )
            raise RuntimeError(
                f"Gemini response body was empty (blockReason={block_reason}, finishReason={finish_reason})"
            )

        raw_candidates = self._loads_candidate_json(text)
        if isinstance(raw_candidates, dict):
            raw_candidates = raw_candidates.get("clips") or raw_candidates.get("candidates") or []
        if not isinstance(raw_candidates, list):
            raise RuntimeError("Gemini response JSON must be an array of candidates")

        candidates: list[ClipCandidate] = []
        for idx, item in enumerate(raw_candidates, start=1):
            if not isinstance(item, dict):
                continue
            try:
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
            except (KeyError, TypeError, ValueError):
                continue

        if not candidates:
            raise RuntimeError("Gemini returned zero valid candidates")
        return candidates

    def _extract_text(self, response_json: dict[str, Any]) -> str:
        candidates = response_json.get("candidates") or []
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        for part in parts:
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
        return ""

    def _loads_candidate_json(self, text: str) -> Any:
        normalized = text.strip()
        try:
            return json.loads(normalized)
        except json.JSONDecodeError:
            if not self.json_repair:
                raise RuntimeError("Gemini returned invalid JSON")
        repaired = self._repair_json_text(normalized)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Gemini returned invalid JSON (repair failed)") from exc

    def _repair_json_text(self, text: str) -> str:
        body = text.strip()
        if body.startswith("```"):
            lines = body.splitlines()
            if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].strip() == "```":
                body = "\n".join(lines[1:-1]).strip()
            if body.lower().startswith("json"):
                body = body[4:].strip()

        array_start = body.find("[")
        array_end = body.rfind("]")
        if array_start != -1 and array_end != -1 and array_start < array_end:
            return body[array_start : array_end + 1]

        object_start = body.find("{")
        object_end = body.rfind("}")
        if object_start != -1 and object_end != -1 and object_start < object_end:
            return body[object_start : object_end + 1]

        return body

    def _build_ssl_context(self) -> ssl.SSLContext:
        try:
            import certifi

            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            return ssl.create_default_context()
