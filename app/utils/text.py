import re
from app.utils.article_normalizer import normalize_article


def extract_article_candidate(text: str) -> str | None:
    m = re.search(r'\b[A-Za-z0-9]{5,}[A-Za-z0-9._\-/]*\b', text)
    return normalize_article(m.group(0)) if m else None
