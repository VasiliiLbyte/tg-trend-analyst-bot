from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.llm.prompts import (
    AnalysisBundle,
    PROMPT_VERSION,
    SYSTEM_EXTRACTION,
    SYSTEM_POST_GENERATION,
    SYSTEM_SYNTHESIS,
    build_extraction_user_prompt,
    build_post_user_prompt,
    build_synthesis_user_prompt,
)

logger = logging.getLogger(__name__)


class OpenRouterError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OpenRouterConfig:
    api_key: str
    base_url: str
    model: str
    timeout_s: float = 45.0


class OpenRouterClient:
    def __init__(self, *, cfg: OpenRouterConfig, http: httpx.AsyncClient | None = None) -> None:
        self._cfg = cfg
        self._http = http

    async def _client(self) -> httpx.AsyncClient:
        if self._http is not None:
            return self._http
        return httpx.AsyncClient(
            base_url=self._cfg.base_url,
            timeout=self._cfg.timeout_s,
            headers={
                "Authorization": f"Bearer {self._cfg.api_key}",
                "Content-Type": "application/json",
            },
        )

    @property
    def model(self) -> str:
        return self._cfg.model

    @property
    def prompt_version(self) -> str:
        return PROMPT_VERSION

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=1, max=10))
    async def chat_json(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 900,
    ) -> dict[str, Any]:
        payload = {
            "model": self._cfg.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        client = await self._client()
        close_after = self._http is None
        try:
            r = await client.post("/chat/completions", json=payload)
            if r.status_code == 401:
                raise OpenRouterError("openrouter_auth_failed")
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError as e:
            logger.warning("openrouter_http_error", extra={"err": str(e)})
            raise
        finally:
            if close_after:
                await client.aclose()

        try:
            content = data["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001
            raise OpenRouterError("openrouter_bad_response_shape") from e

        if isinstance(content, dict):
            return content
        if isinstance(content, str):
            import json

            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                raise OpenRouterError("openrouter_non_json_content") from e

        raise OpenRouterError("openrouter_unknown_content_type")

    async def analyze_news_item(
        self,
        *,
        title: str,
        url: str,
        summary: str | None,
    ) -> AnalysisBundle:
        """
        3-stage analysis:
        extraction -> synthesis -> post_generation
        """
        extraction_user = build_extraction_user_prompt(title=title, url=url, summary=summary)
        from app.llm.prompts import ExtractionResult, PostGenerationResult, SynthesisResult

        extraction_raw = await self.chat_json(
            system=SYSTEM_EXTRACTION,
            user=extraction_user,
            temperature=0.1,
            max_tokens=900,
        )
        extraction = ExtractionResult.model_validate(extraction_raw)

        import json

        extraction_json = json.dumps(extraction.model_dump(), ensure_ascii=False)
        synthesis_user = build_synthesis_user_prompt(extraction_json=extraction_json)
        synthesis_raw = await self.chat_json(
            system=SYSTEM_SYNTHESIS,
            user=synthesis_user,
            temperature=0.2,
            max_tokens=900,
        )
        synthesis = SynthesisResult.model_validate(synthesis_raw)

        synthesis_json = json.dumps(synthesis.model_dump(), ensure_ascii=False)
        post_user = build_post_user_prompt(title=title, url=url, synthesis_json=synthesis_json)
        post_raw = await self.chat_json(
            system=SYSTEM_POST_GENERATION,
            user=post_user,
            temperature=0.4,
            max_tokens=1200,
        )
        post = PostGenerationResult.model_validate(post_raw)

        return AnalysisBundle(extraction=extraction, synthesis=synthesis, post=post)

