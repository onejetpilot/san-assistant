from fastapi.testclient import TestClient

from app.api.main import app
from app.api import routes_chat


client = TestClient(app)


def test_chat_endpoint_rejects_empty_message():
    resp = client.post('/api/chat', json={'message': '   ', 'session_id': None, 'answer_style': 'short'})
    assert resp.status_code == 422


def test_chat_endpoint_rejects_too_long_message():
    resp = client.post('/api/chat', json={'message': 'x' * 2001, 'session_id': None, 'answer_style': 'short'})
    assert resp.status_code == 422


def test_chat_endpoint_returns_service_payload(monkeypatch):
    async def _answer(message, session_id=None, answer_style='detailed', conversation_id=None):
        return {
            'session_id': 's1',
            'conversation_id': conversation_id or 'c1',
            'request_id': 'r1',
            'answer': f'echo:{message}',
            'original_query': message,
            'resolved_query': message,
            'depends_on_history': False,
            'answer_mode': 'short_answer',
            'sources': [],
            'documents': [],
            'used_web_search': False,
            'web_results': [],
            'confidence': 'high',
            'tools_used': ['smalltalk'],
            'retrieval_trace': [{
                'status': 'ok',
                'query': message,
                'count': 1,
                'results': [{'x': 1}],
                'note': '',
                'error': '',
                'meta': {'tool': 'smalltalk'},
                'mode': 'test',
            }],
            'route': {'intent': 'smalltalk'},
        }

    monkeypatch.setattr(routes_chat.service, 'answer', _answer)

    resp = client.post('/api/chat', json={'message': 'привет', 'session_id': None, 'answer_style': 'short'})
    assert resp.status_code == 200
    body = resp.json()
    assert body['answer'] == 'echo:привет'
    assert body['session_id'] == 's1'
    assert body['conversation_id'] == 'c1'
    assert body['retrieval_trace'][0]['meta']['tool'] == 'smalltalk'
    assert body['route']['intent'] == 'smalltalk'


def test_chat_endpoint_returns_safe_500(monkeypatch):
    async def _answer(*args, **kwargs):
        raise RuntimeError('boom')

    monkeypatch.setattr(routes_chat.service, 'answer', _answer)

    resp = client.post('/api/chat', json={'message': 'привет', 'session_id': None, 'answer_style': 'short'})
    assert resp.status_code == 500
    assert 'Не удалось обработать сообщение' in resp.json()['detail']
