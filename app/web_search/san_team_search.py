from app.core.config import settings


class SanTeamSearch:
    async def search(self, query: str) -> list[dict]:
        if not settings.WEB_SEARCH_API_KEY:
            return []
        scoped = f'site:san.team {query}'
        _ = scoped
        return []
