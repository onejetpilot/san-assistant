from uuid import uuid4

from app.storage.db import init_db
from app.services.conversation_memory import ConversationMemoryService


def test_conversation_memory_isolated_by_conversation_id():
    init_db()
    memory = ConversationMemoryService()
    session_id = memory.ensure_session(f'test-session-{uuid4()}')
    conv_a = memory.ensure_conversation(session_id, f'test-conv-a-{uuid4()}')
    conv_b = memory.ensure_conversation(session_id, f'test-conv-b-{uuid4()}')

    memory.append_message(session_id, conv_a, role='user', content='сообщение A')
    memory.append_message(session_id, conv_b, role='user', content='сообщение B')
    memory.update_state(conv_a, session_id, current_article='ART-A')
    memory.update_state(conv_b, session_id, current_article='ART-B')

    messages_a = memory.get_recent_messages(conv_a, session_id=session_id)
    messages_b = memory.get_recent_messages(conv_b, session_id=session_id)

    assert [m['content'] for m in messages_a] == ['сообщение A']
    assert [m['content'] for m in messages_b] == ['сообщение B']
    assert memory.get_state(conv_a, session_id=session_id)['current_article'] == 'ART-A'
    assert memory.get_state(conv_b, session_id=session_id)['current_article'] == 'ART-B'
