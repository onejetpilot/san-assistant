import json

import httpx

from app.core.config import settings


class OpenAICompatibleLLMClient:
    def __init__(self) -> None:
        self.base_url = settings.ROUTERAI_BASE_URL.rstrip('/')
        self.api_key = settings.ROUTERAI_API_KEY

    def _build_payload(self, system_prompt: str, user_prompt: str, model: str | None = None, temperature: float | None = None) -> dict:
        return {
            'model': model or settings.LLM_MODEL,
            'temperature': settings.LLM_TEMPERATURE if temperature is None else temperature,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
        }

    async def chat(self, system_prompt: str, user_prompt: str, model: str | None = None, temperature: float | None = None) -> str:
        if not self.api_key:
            return 'LLM не настроен. Проверьте ROUTERAI_API_KEY.'
        payload = self._build_payload(system_prompt, user_prompt, model=model, temperature=temperature)
        headers = {'Authorization': f'Bearer {self.api_key}'}
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            r = await client.post(f'{self.base_url}/chat/completions', json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            return data['choices'][0]['message']['content']

    @staticmethod
    def _extract_delta_text(data: dict) -> str:
        choices = data.get('choices') or []
        if not choices:
            return ''
        choice = choices[0] or {}
        delta = choice.get('delta') or {}
        if isinstance(delta, dict) and delta.get('content'):
            return str(delta['content'])
        message = choice.get('message') or {}
        if isinstance(message, dict) and message.get('content'):
            return str(message['content'])
        text = choice.get('text')
        return str(text) if text else ''

    async def stream_chat(self, system_prompt: str, user_prompt: str, model: str | None = None, temperature: float | None = None):
        if not self.api_key:
            yield 'LLM не настроен. Проверьте ROUTERAI_API_KEY.'
            return

        payload = self._build_payload(system_prompt, user_prompt, model=model, temperature=temperature)
        payload['stream'] = True
        headers = {'Authorization': f'Bearer {self.api_key}'}

        try:
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
                async with client.stream('POST', f'{self.base_url}/chat/completions', json=payload, headers=headers) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        raw = line.strip()
                        if not raw or raw.startswith(':') or raw.startswith('event:'):
                            continue
                        if raw.startswith('data:'):
                            raw = raw[5:].strip()
                        if raw == '[DONE]':
                            break
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        delta_text = self._extract_delta_text(data)
                        if delta_text:
                            yield delta_text
        except Exception:
            fallback = await self.chat(system_prompt, user_prompt, model=model, temperature=temperature)
            if fallback:
                yield fallback
