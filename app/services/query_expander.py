from pathlib import Path
import yaml


class QueryExpander:
    def __init__(self, path: str = 'app/core/synonyms.yml') -> None:
        p = Path(path)
        data = yaml.safe_load(p.read_text(encoding='utf-8')) if p.exists() else {'synonyms': {}}
        self.synonyms = data.get('synonyms', {})

    def expand(self, query: str) -> str:
        ql = query.lower()
        add: list[str] = []
        for key, vals in self.synonyms.items():
            key_l = key.lower()
            if key_l in ql or any(v.lower() in ql for v in vals):
                add.extend([key] + vals)
        if not add:
            return query
        return query + ' | synonyms: ' + ', '.join(sorted(set(add)))
