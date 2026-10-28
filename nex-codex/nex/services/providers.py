import httpx
from ..security import DomainError


class AIProvider:
    """Optional OpenAI-compatible chat completions adapter; disabled without configuration."""
    def __init__(self, settings):
        self.settings = settings

    async def ask(self, prompt):
        cfg = self.settings
        if not cfg.ai_api_key or not cfg.ai_model:
            raise DomainError('AI is not configured. Ask the owner to set AI_API_KEY and AI_MODEL.')
        if not 1 <= len(prompt) <= 2000:
            raise DomainError('Prompts must be 1–2000 characters.')
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(cfg.ai_base_url.rstrip('/') + '/chat/completions', headers={'Authorization': f'Bearer {cfg.ai_api_key}'}, json={'model': cfg.ai_model, 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 500})
                response.raise_for_status()
                return response.json()['choices'][0]['message']['content'][:3900]
        except (httpx.HTTPError, KeyError, ValueError, IndexError, TypeError) as exc:
            raise DomainError('The AI provider is unavailable. Try again later.') from exc
