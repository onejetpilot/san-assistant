import pytest

from app.services.router import rule_based_router


def test_article_to_sku():
    r = rule_based_router('Найди ABC12345')
    assert 'sku_lookup' in r['tools']


def test_passport_to_documents():
    r = rule_based_router('нужен паспорт на изделие')
    assert 'document_search' in r['tools']


def test_san_team_route():
    r = rule_based_router('поищи на san.team')
    assert r['intent'] == 'san_team_search'


def test_offtopic_refuse():
    r = rule_based_router('какая погода завтра')
    assert r['intent'] == 'offtopic'
