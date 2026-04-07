from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI

from app.extractors.llm import (
    LLMClient,
    LLMGenerationRequest,
    LLMGenerationResponse,
)
from app.settings import get_settings


@dataclass(slots=True)
class OpenAILLMClient(LLMClient):
    """
    OpenAI-backed implementation of the LLM extraction client.

    This client asks the model to return one JSON object with:
      - value: the extracted payload
      - confidence: optional confidence score
      - error: optional extraction failure message
    """

    api_key: str
    model: str = "gpt-4.1-mini"
    base_url: str | None = None
    timeout_seconds: float = 60.0
    reasoning_effort: str | None = None

    _client: AsyncOpenAI = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout_seconds,
        )

    @classmethod
    def from_env(cls) -> "OpenAILLMClient | None":
        settings = get_settings().openai
        if not settings.api_key:
            return None

        return cls(
            api_key=settings.api_key,
            base_url=settings.base_url,
            model=settings.model,
            timeout_seconds=settings.timeout_seconds,
            reasoning_effort=settings.reasoning_effort,
        )

    async def generate_structured(
        self,
        request: LLMGenerationRequest,
    ) -> LLMGenerationResponse:
        if not request.content.strip():
            return LLMGenerationResponse(
                success=False,
                error_message="LLM request content must not be empty.",
            )

        system_prompt = (
            "You are a precise information extraction system. "
            "Return exactly one valid JSON object and no markdown. "
            'The JSON object must contain keys "value", "confidence", and "error". '
            '"value" may be an object, array, string, number, boolean, or null. '
            '"confidence" must be a number between 0 and 1 or null. '
            '"error" must be a short string or null.'
        )

        schema_hint = (
            f"Target schema name: {request.output_schema_name}\n"
            if request.output_schema_name
            else ""
        )

        user_prompt = (
            f"{schema_hint}Instruction:\n{request.instruction}\n\n"
            "Source content:\n"
            f"{request.content}\n\n"
            "If the requested information is absent or cannot be extracted "
            'reliably, return {"value": null, "confidence": null, "error": "..."}.'
        )

        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
            "text": {"format": {"type": "json_object"}},
        }

        if self.reasoning_effort:
            request_kwargs["reasoning"] = {"effort": self.reasoning_effort}

        try:
            response = await self._client.responses.create(**request_kwargs)
        except Exception as exc:
            return LLMGenerationResponse(
                success=False,
                error_message=f"OpenAI request failed: {exc}",
            )

        raw_text = self._response_text(response)
        if not raw_text:
            return LLMGenerationResponse(
                success=False,
                error_message="OpenAI response did not contain any output text.",
            )

        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            return LLMGenerationResponse(
                success=False,
                raw_text=raw_text,
                error_message=f"OpenAI response was not valid JSON: {exc}",
            )

        if not isinstance(payload, dict):
            return LLMGenerationResponse(
                success=False,
                raw_text=raw_text,
                error_message="OpenAI response JSON must be an object.",
            )

        error_message = payload.get("error")
        confidence = payload.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = None

        if error_message:
            return LLMGenerationResponse(
                success=False,
                value=payload.get("value"),
                raw_text=raw_text,
                confidence=confidence,
                error_message=str(error_message),
            )

        return LLMGenerationResponse(
            success=True,
            value=payload.get("value"),
            raw_text=raw_text,
            confidence=confidence,
        )

    def _response_text(self, response: Any) -> str | None:
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        output = getattr(response, "output", None)
        if not isinstance(output, list):
            return None

        parts: list[str] = []
        for item in output:
            content = getattr(item, "content", None)
            if not isinstance(content, list):
                continue

            for block in content:
                text = getattr(block, "text", None)
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())

        if not parts:
            return None

        return "\n".join(parts)
