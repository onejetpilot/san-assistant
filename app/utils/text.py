import re

from app.utils.article_normalizer import normalize_article

KNOWN_BRANDS = {'ONDO', 'STM', 'OPTIMA', 'ROEGEN', 'VALTEC', 'RISPA', 'ATLASPLAST'}
ARTICLE_RE = re.compile(r'\b[A-Za-z0-9]{5,}[A-Za-z0-9._\-/]*\b')


def _looks_like_article_token(value: str) -> bool:
    normalized = normalize_article(value)
    if normalized in KNOWN_BRANDS:
        return False
    return len(normalized) >= 5 and any(ch.isdigit() for ch in normalized)


def extract_article_candidate(text: str) -> str | None:
    for match in ARTICLE_RE.finditer(text):
        token = match.group(0)
        if _looks_like_article_token(token):
            return normalize_article(token)
    return None
