from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

PROMPT_VERSION = "v2"


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    facts: list[str] = Field(min_length=1)
    key_signals: list[str] = Field(min_length=1)
    entities: list[str] = Field(default_factory=list)
    claims_to_verify: list[str] = Field(default_factory=list)


class SynthesisResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    why_now: str = Field(min_length=1)
    business_angles: list[str] = Field(min_length=1)
    risks: list[str] = Field(default_factory=list)
    future_signals: list[str] = Field(default_factory=list)


class PostGenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    headline: str = Field(min_length=1)
    hook: str = Field(min_length=1)
    bullet_points: list[str] = Field(min_length=3, max_length=12)
    what_to_do: list[str] = Field(min_length=1, max_length=7)
    why_now: str = Field(min_length=1)
    sources: list[str] = Field(min_length=1)


class AnalysisBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    extraction: ExtractionResult
    synthesis: SynthesisResult
    post: PostGenerationResult


SYSTEM_EXTRACTION = """You are a meticulous analyst. Return ONLY valid JSON (no markdown).

Task: extract concrete facts and signals from the provided news item.
Rules:
- Be specific and grounded in the input.
- If input is thin, write fewer but higher-confidence facts.

Return JSON with schema:
{
  "facts": ["..."],
  "key_signals": ["..."],
  "entities": ["..."],
  "claims_to_verify": ["..."]
}
"""

SYSTEM_SYNTHESIS = """You are a strategy analyst. Return ONLY valid JSON (no markdown).

Task: synthesize implications for business/tech trends based on extracted facts/signals.
Rules:
- No hype. Prefer concrete implications and second-order effects.

Return JSON with schema:
{
  "why_now": "...",
  "business_angles": ["..."],
  "risks": ["..."],
  "future_signals": ["..."]
}
"""

SYSTEM_POST_GENERATION = """You are a Telegram channel editor. Return ONLY valid JSON (no markdown).

Task: produce a beautiful, skimmable Telegram post draft in Russian.
Rules:
- Keep it concise, actionable, and credible.
- Use short bullet points; avoid excessive emojis.

Return JSON with schema:
{
  "headline": "...",
  "hook": "...",
  "bullet_points": ["..."],
  "what_to_do": ["..."],
  "why_now": "...",
  "sources": ["https://..."]
}
"""


def build_extraction_user_prompt(*, title: str, url: str, summary: str | None) -> str:
    s = summary or ""
    return f"""Title: {title}
URL: {url}
Summary: {s}
"""


def build_synthesis_user_prompt(*, extraction_json: str) -> str:
    return f"""Extraction JSON:
{extraction_json}
"""


def build_post_user_prompt(*, title: str, url: str, synthesis_json: str) -> str:
    return f"""News item:
Title: {title}
URL: {url}

Synthesis JSON:
{synthesis_json}
"""

