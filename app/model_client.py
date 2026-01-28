#!/usr/bin/env python3
"""
Model Client - Unified async LLM completion interface.
Routes requests to Anthropic (Claude) or OpenAI-compatible APIs (Ollama, vLLM, etc.)
based on personality configuration.
"""

from dataclasses import dataclass
from typing import Optional, Union


@dataclass
class CompletionResult:
    """Unified result from any LLM provider."""
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    is_local: bool  # True = no API cost (e.g. Ollama)


class ModelClient:
    """Routes async LLM completions to the appropriate provider."""

    def __init__(self, anthropic_client):
        self.anthropic = anthropic_client
        self._openai_clients = {}  # base_url -> AsyncOpenAI client (lazy-init)

    def _get_openai_client(self, base_url: str, api_key: str = 'ollama'):
        """Get or create an async OpenAI-compatible client for a base URL."""
        if base_url not in self._openai_clients:
            from openai import AsyncOpenAI
            self._openai_clients[base_url] = AsyncOpenAI(
                base_url=base_url,
                api_key=api_key,
            )
        return self._openai_clients[base_url]

    async def complete(
        self,
        personality: dict,
        system: Union[list, str],
        messages: list,
        max_tokens: int = 800,
        temperature: float = 1.0,
        model_override: Optional[str] = None,
    ) -> CompletionResult:
        """
        Send an async completion request to the appropriate provider.

        Args:
            personality: Personality config dict (provider, model, base_url, etc.)
            system: System prompt - list of blocks for Anthropic, string for OpenAI-compatible
            messages: Conversation messages in [{role, content}] format
            max_tokens: Max output tokens
            temperature: Sampling temperature
            model_override: Override the personality's model (used for Anthropic model routing)

        Returns:
            CompletionResult with response text and usage info
        """
        provider = personality.get('provider', 'anthropic')

        if provider == 'anthropic':
            return await self._complete_anthropic(
                personality, system, messages, max_tokens, temperature, model_override
            )
        elif provider == 'openai_compatible':
            return await self._complete_openai(
                personality, system, messages, max_tokens, temperature
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def _complete_anthropic(
        self, personality: dict, system: Union[list, str],
        messages: list, max_tokens: int, temperature: float,
        model_override: Optional[str] = None,
    ) -> CompletionResult:
        """Complete using the Anthropic API (Claude)."""
        model = model_override or personality.get('model') or 'claude-sonnet-4-5-20250929'

        response = await self.anthropic.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=messages,
        )

        return CompletionResult(
            text=response.content[0].text.strip(),
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            is_local=False,
        )

    async def _complete_openai(
        self, personality: dict, system: Union[list, str],
        messages: list, max_tokens: int, temperature: float,
    ) -> CompletionResult:
        """Complete using an OpenAI-compatible API (Ollama, vLLM, etc.)."""
        base_url = personality['base_url']
        api_key = personality.get('api_key', 'ollama')
        model = personality['model']

        client = self._get_openai_client(base_url, api_key)

        # Build messages list with system prompt
        system_text = system if isinstance(system, str) else personality.get('system_prompt', 'You are a helpful assistant.')
        oai_messages = [{"role": "system", "content": system_text}]

        for msg in messages:
            oai_messages.append({
                "role": msg["role"],
                "content": msg["content"] if isinstance(msg["content"], str) else str(msg["content"]),
            })

        response = await client.chat.completions.create(
            model=model,
            messages=oai_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        usage = response.usage
        return CompletionResult(
            text=response.choices[0].message.content.strip(),
            model=model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            is_local=True,
        )
