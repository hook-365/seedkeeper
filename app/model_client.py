#!/usr/bin/env python3
"""
Model Client - Async LLM completion interface for OpenAI-compatible APIs (Ollama, vLLM, etc.)
Local-only - no external API dependencies.
"""

from dataclasses import dataclass
from typing import Optional, Union


@dataclass
class CompletionResult:
    """Result from LLM completion."""
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    is_local: bool = True  # Always True for local models


class ModelClient:
    """Routes async LLM completions to OpenAI-compatible APIs (Ollama, etc.)."""

    def __init__(self):
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
        system: str,
        messages: list,
        max_tokens: int = 800,
        temperature: float = 1.0,
    ) -> CompletionResult:
        """
        Send an async completion request to the OpenAI-compatible API.

        Args:
            personality: Personality config dict (model, base_url, etc.)
            system: System prompt string
            messages: Conversation messages in [{role, content}] format
            max_tokens: Max output tokens
            temperature: Sampling temperature

        Returns:
            CompletionResult with response text and usage info
        """
        base_url = personality['base_url']
        api_key = personality.get('api_key', 'ollama')
        model = personality['model']

        client = self._get_openai_client(base_url, api_key)

        # Build system prompt - prefer personality's system_prompt, then use provided
        if personality.get('system_prompt'):
            system_text = personality['system_prompt']
        elif isinstance(system, str) and system:
            system_text = system
        else:
            system_text = 'You are a helpful assistant.'

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
