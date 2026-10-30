"""The chat agent: Claude via Pydantic AI, plus conversion of stored messages into its history."""

from collections.abc import Sequence
from functools import lru_cache

from pydantic_ai import Agent, ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
from pydantic_ai.providers.anthropic import AnthropicProvider

from mgpa_backend.config import get_settings
from mgpa_backend.models import Message, MessageRole

INSTRUCTIONS = """\
You are MGPA, a personal assistant for a single user: a master's student in Management & \
Technology who is applying for engineering roles.
Answer in the language the user writes in. Be concise and concrete; use Markdown when it helps.
If you don't know something, say so instead of guessing.\
"""

# Upper bound for one answer. Only generated tokens are billed, so this is a safety cap,
# not a cost; long enough that normal answers are never cut off.
MAX_OUTPUT_TOKENS = 16_000


@lru_cache
def get_agent() -> Agent[None, str]:
    """Build the agent once. Model ID, API key and effort come from the settings (.env)."""
    settings = get_settings()
    model = AnthropicModel(
        settings.anthropic_model,
        provider=AnthropicProvider(api_key=settings.anthropic_api_key.get_secret_value()),
    )
    return Agent(
        model,
        instructions=INSTRUCTIONS,
        model_settings=AnthropicModelSettings(
            max_tokens=MAX_OUTPUT_TOKENS,
            anthropic_thinking={"type": "adaptive"},
            anthropic_effort=settings.anthropic_effort,
        ),
    )


def to_model_history(messages: Sequence[Message]) -> list[ModelMessage]:
    """Translate our stored messages into the format Pydantic AI sends to Claude as history."""
    history: list[ModelMessage] = []
    for message in messages:
        if message.role == MessageRole.USER:
            history.append(ModelRequest(parts=[UserPromptPart(content=message.content)]))
        else:
            history.append(ModelResponse(parts=[TextPart(content=message.content)]))
    return history
