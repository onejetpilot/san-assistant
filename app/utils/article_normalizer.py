from __future__ import annotations

import re
from dataclasses import dataclass


RUS_TO_LAT = str.maketrans({
    'О': 'O', 'Х': 'X', 'С': 'C', 'А': 'A', 'Е': 'E', 'Р': 'P', 'Т': 'T', 'М': 'M', 'К': 'K', 'Н': 'H', 'В': 'B',
    'о': 'O', 'х': 'X', 'с': 'C', 'а': 'A', 'е': 'E', 'р': 'P', 'т': 'T', 'м': 'M', 'к': 'K', 'н': 'H', 'в': 'B',
})
KIT_SUFFIX_RE = re.compile(r'^(?P<base>[A-Z0-9._/-]+?)(?P<suffix>K\d+)(?P<trailing>[A-Z]*)$')


@dataclass(frozen=True)
class NormalizedSku:
    original: str
    normalized: str
    base_article: str
    had_kit_suffix: bool = False


def normalize_article(value: str | None) -> str:
    if not value:
        return ''
    v = value.translate(RUS_TO_LAT)
    v = v.replace(' ', '').replace('-', '').upper()
    return v


def normalize_sku(value: str | None) -> NormalizedSku:
    normalized = normalize_article(value)
    if not normalized:
        return NormalizedSku(original=value or '', normalized='', base_article='', had_kit_suffix=False)
    match = KIT_SUFFIX_RE.match(normalized)
    if not match:
        return NormalizedSku(original=value or '', normalized=normalized, base_article=normalized, had_kit_suffix=False)
    base_article = f"{match.group('base')}{match.group('trailing')}"
    return NormalizedSku(
        original=value or '',
        normalized=normalized,
        base_article=base_article,
        had_kit_suffix=True,
    )
