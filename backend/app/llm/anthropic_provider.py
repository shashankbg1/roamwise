"""Claude as the model backend, through the Anthropic API or AWS Bedrock."""

from typing import Any

from anthropic import APIError, AsyncAnthropic, AsyncAnthropicBedrockMantle

from app.llm.base import LLMError, T, Task

MAX_TOKENS = 16000


class AnthropicProvider:
    """Calls Claude with structured outputs so every answer is validated against a schema."""

    def __init__(self, model: str, *, bedrock_region: str | None = None) -> None:
        if bedrock_region:
            self.name = "bedrock"
            self._client = AsyncAnthropicBedrockMantle(aws_region=bedrock_region)
            # Bedrock model ids carry an "anthropic." prefix.
            self._model = model if model.startswith("anthropic.") else f"anthropic.{model}"
        else:
            self.name = "anthropic"
            self._client = AsyncAnthropic()  # reads ANTHROPIC_API_KEY from the environment
            self._model = model

    async def generate(
        self,
        *,
        task: Task,
        system: str,
        prompt: str,
        schema: type[T],
        context: dict[str, Any],
    ) -> T:
        try:
            response = await self._client.messages.parse(
                model=self._model,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_format=schema,
            )
        except APIError as exc:
            raise LLMError(f"{task}: model call failed: {exc}") from exc
        if response.stop_reason == "refusal":
            raise LLMError(f"{task}: the model declined this request")
        if response.stop_reason == "max_tokens" or response.parsed_output is None:
            raise LLMError(f"{task}: the model returned an incomplete answer")
        return response.parsed_output
