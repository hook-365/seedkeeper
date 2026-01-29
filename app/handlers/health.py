"""Health check command handler."""

import json
import urllib.request
from datetime import datetime
from typing import Dict, Any, Optional


class HealthHandler:
    def __init__(self, bot):
        self.bot = bot

    def _get_ollama_model_info(self, base_url: str, model: str) -> Optional[dict]:
        """Fetch model info from Ollama API."""
        try:
            # Convert OpenAI-style URL to Ollama native
            api_url = base_url.replace('/v1', '') + '/api/show'
            req = urllib.request.Request(
                api_url,
                data=json.dumps({"name": model}).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception:
            return None

    async def handle_health_command(self, command_data: Dict[str, Any]):
        """Handle !health command."""
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)
        author_id = command_data.get('author_id')

        # Get current model info from personality manager
        personality = self.bot.personality_manager.get_default()
        model_display = personality.get('display_name', 'Unknown')
        model_name = personality.get('model', 'default')
        provider = personality.get('provider', 'unknown')
        is_local = provider == 'openai_compatible'

        health_text = f"""**Seedkeeper Health**

**System**
- Status: {"Online" if self.bot.is_ready() else "Offline"}
- Latency: {self.bot.latency*1000:.0f}ms

**Model**
- {model_display}
- Engine: `{model_name}`"""

        if is_local:
            health_text += "\n- Type: Local (no API cost)"

            # Get nerdy Ollama details
            base_url = personality.get('base_url', '')
            ollama_info = self._get_ollama_model_info(base_url, model_name)

            if ollama_info:
                details = ollama_info.get('details', {})
                model_info = ollama_info.get('model_info', {})

                params = details.get('parameter_size', '?')
                quant = details.get('quantization_level', '?')
                ctx = model_info.get('qwen2.context_length', model_info.get('llama.context_length', '?'))
                family = details.get('family', '?')

                health_text += f"""

**Architecture**
- Parameters: {params}
- Quantization: {quant}
- Context: {ctx:,} tokens
- Family: {family}
- Format: {details.get('format', 'gguf')}"""

            # Show personality settings
            memory_limit = personality.get('memory_limit', 5)
            max_tokens = personality.get('max_tokens', 800)
            health_text += f"""

**Settings**
- Memory depth: {memory_limit} messages
- Max response: {max_tokens} tokens"""

        else:
            health_text += "\n- Type: Cloud API"
            perspective_count = len(self.bot._views_manager.get_all_perspectives())
            health_text += f"\n\n**Knowledge Base**\n- {perspective_count} Lightward perspectives"

        health_text += f"\n\n*{datetime.utcnow().strftime('%H:%M UTC')}*"

        await self.bot.send_message(channel_id, health_text, is_dm=is_dm, author_id=author_id)
