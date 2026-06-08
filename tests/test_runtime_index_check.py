import json

import pytest

from app.evaluation import check_runtime_indexes as mod


class _Collection:
    def __init__(self, count: int):
        self._count = count

    def count(self) -> int:
        return self._count


class _Client:
    def get_or_create_collection(self, name, embedding_function=None):
        counts = {
            'product_chunks': 3,
            'documents': 0,
            'product_cards': 2,
        }
        return _Collection(counts[name])


def test_invalid_component_rows_detects_dirty_legacy_components():
    data = {
        'OXF01612': {'kit_components': ['диаметр']},
        'OXF01612K10G': {'kit_components': ['10 шт OXF01612', '10 шт OXS00016']},
    }

    assert mod._invalid_component_rows(data, 'kit_components') == ['OXF01612']


def test_check_runtime_indexes_fails_on_dirty_indexes(tmp_path, monkeypatch):
    (tmp_path / 'sku_index.json').write_text(json.dumps({
        'OXF01612': {'kit_components': ['диаметр']},
    }), encoding='utf-8')
    (tmp_path / 'kit_index.json').write_text(json.dumps({
        'OXF01612': {'components': ['диаметр']},
    }), encoding='utf-8')

    monkeypatch.setattr(mod.settings, 'INDEXES_PATH', str(tmp_path))
    monkeypatch.setattr(mod, 'get_chroma_client', lambda: _Client())

    with pytest.raises(RuntimeError) as exc:
        mod.check_runtime_indexes()

    message = str(exc.value)
    assert 'dirty_sku_count' in message
    assert 'dirty_kit_count' in message


def test_check_runtime_indexes_passes_clean_indexes(tmp_path, monkeypatch):
    (tmp_path / 'sku_index.json').write_text(json.dumps({
        'OXF01612K10G': {'kit_components': ['10 шт OXF01612', '10 шт OXS00016']},
    }), encoding='utf-8')
    (tmp_path / 'kit_index.json').write_text(json.dumps({
        'OXF01612K10G': {'components': ['10 шт OXF01612', '10 шт OXS00016']},
    }), encoding='utf-8')

    monkeypatch.setattr(mod.settings, 'INDEXES_PATH', str(tmp_path))
    monkeypatch.setattr(mod, 'get_chroma_client', lambda: _Client())

    result = mod.check_runtime_indexes()

    assert result['status'] == 'ok'
    assert result['dirty_sku_count'] == 0
    assert result['dirty_kit_count'] == 0
