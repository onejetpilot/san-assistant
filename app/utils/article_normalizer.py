RUS_TO_LAT = str.maketrans({
    'О': 'O', 'Х': 'X', 'С': 'C', 'А': 'A', 'Е': 'E', 'Р': 'P', 'Т': 'T', 'М': 'M', 'К': 'K', 'Н': 'H', 'В': 'B',
    'о': 'O', 'х': 'X', 'с': 'C', 'а': 'A', 'е': 'E', 'р': 'P', 'т': 'T', 'м': 'M', 'к': 'K', 'н': 'H', 'в': 'B',
})


def normalize_article(value: str | None) -> str:
    if not value:
        return ''
    v = value.translate(RUS_TO_LAT)
    v = v.replace(' ', '').replace('-', '').upper()
    return v
