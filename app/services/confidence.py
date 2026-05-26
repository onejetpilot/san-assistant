def compute_confidence(sku_found: bool, rag_scores: list[float], docs_found: bool, used_web_only: bool = False) -> dict:
    if sku_found:
        return {'label': 'high', 'score': 0.95, 'reason': 'exact article match'}
    top = max(rag_scores) if rag_scores else 0.0
    if docs_found and top > 0.35:
        return {'label': 'high', 'score': 0.85, 'reason': 'rag+documents'}
    if top > 0.6:
        return {'label': 'high', 'score': 0.8, 'reason': 'strong rag'}
    if top > 0.35:
        return {'label': 'medium', 'score': 0.55, 'reason': 'partial semantic match'}
    if used_web_only:
        return {'label': 'low', 'score': 0.25, 'reason': 'web fallback only'}
    return {'label': 'low', 'score': 0.2, 'reason': 'weak local evidence'}
