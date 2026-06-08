import asyncio

from app.services.routing.router import route_query


def test_route_query_uses_resolved_query_for_follow_up_context(monkeypatch):
    monkeypatch.setattr('app.services.routing.router.settings.ROUTER_MODE', 'rules')

    resolved = 'Подойдет ли он? Контекст текущего диалога: артикул OXF01612, продукт Фитинги ONDO.'
    decision = asyncio.run(route_query(
        resolved,
        original_query='Подойдет ли он?',
        conversation_state={'current_article': 'OXF01612', 'current_product': 'Фитинги ONDO'},
        recent_messages=[],
    ))

    assert decision.intent == 'follow_up'
    assert decision.use_history is True
