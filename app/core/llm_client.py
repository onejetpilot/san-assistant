import httpx

from app.core.config import settings


class OpenAICompatibleLLMClient:
    def __init__(self) -> None:
        self.base_url = settings.ROUTERAI_BASE_URL.rstrip('/')
        self.api_key = settings.ROUTERAI_API_KEY

    async def chat(self, system_prompt: str, user_prompt: str, model: str | None = None, temperature: float | None = None) -> str:
        if not self.api_key:
            return 'LLM не настроен. Проверьте ROUTERAI_API_KEY.'
        payload = {
            'model': model or settings.LLM_MODEL,
            'temperature': settings.LLM_TEMPERATURE if temperature is None else temperature,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
        }
        headers = {'Authorization': f'Bearer {self.api_key}'}
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            r = await client.post(f'{self.base_url}/chat/completions', json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            return data['choices'][0]['message']['content']
