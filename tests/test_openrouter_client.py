from __future__ import annotations

import json

import httpx
import pytest

from app.llm.openrouter import OpenRouterClient, OpenRouterConfig


@pytest.mark.asyncio
async def test_openrouter_client_parses_json_string() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        body = json.loads(request.content.decode("utf-8"))
        assert body["response_format"]["type"] == "json_object"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "key_points": ["a"],
                                    "why_now": "b",
                                    "business_angles": [],
                                    "risks": [],
                                    "signals": [],
                                }
                            )
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="https://openrouter.ai/api/v1")
    client = OpenRouterClient(
        cfg=OpenRouterConfig(api_key="x", base_url="https://openrouter.ai/api/v1", model="m"),
        http=http,
    )

    out = await client.chat_json(system="s", user="u")
    assert out["why_now"] == "b"
