from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
Base = declarative_base()


_SCHEMA_UPGRADES = {
    'chat_requests': [
        ('conversation_id', 'conversation_id VARCHAR(64)'),
    ],
    'chat_messages': [
        ('conversation_id', 'conversation_id VARCHAR(64)'),
    ],
    'conversation_state': [
        ('conversation_id', 'conversation_id VARCHAR(64)'),
    ],
}

_INDEX_UPGRADES = [
    'CREATE INDEX IF NOT EXISTS ix_chat_requests_conversation_id ON chat_requests (conversation_id)',
    'CREATE INDEX IF NOT EXISTS ix_chat_messages_conversation_id ON chat_messages (conversation_id)',
    'CREATE INDEX IF NOT EXISTS ix_conversation_state_session_id ON conversation_state (session_id)',
    'CREATE UNIQUE INDEX IF NOT EXISTS ix_conversation_state_conversation_id ON conversation_state (conversation_id)',
]


def _conversation_state_has_unique_session_id() -> bool:
    if engine.dialect.name != 'sqlite':
        return False
    inspector = inspect(engine)
    if 'conversation_state' not in set(inspector.get_table_names()):
        return False
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA index_list('conversation_state')")).mappings().all()
        for row in rows:
            if not row.get('unique'):
                continue
            index_name = row.get('name')
            cols = conn.execute(text(f"PRAGMA index_info('{index_name}')")).mappings().all()
            if [col.get('name') for col in cols] == ['session_id']:
                return True
    return False


def _rebuild_conversation_state_without_session_unique() -> None:
    if not _conversation_state_has_unique_session_id():
        return
    with engine.begin() as conn:
        conn.execute(text('ALTER TABLE conversation_state RENAME TO conversation_state_old_unique_session'))
        conn.execute(text(
            '''
            CREATE TABLE conversation_state (
                id INTEGER NOT NULL PRIMARY KEY,
                session_id VARCHAR(64) NOT NULL,
                conversation_id VARCHAR(64),
                current_product TEXT,
                current_brand VARCHAR(128),
                current_article VARCHAR(128),
                current_category VARCHAR(256),
                current_doc_id VARCHAR(256),
                last_intent VARCHAR(64),
                last_answer_mode VARCHAR(64),
                last_sources_json JSON,
                last_documents_json JSON,
                updated_at DATETIME NOT NULL
            )
            '''
        ))
        conn.execute(text(
            '''
            INSERT INTO conversation_state (
                id, session_id, conversation_id, current_product, current_brand, current_article,
                current_category, current_doc_id, last_intent, last_answer_mode,
                last_sources_json, last_documents_json, updated_at
            )
            SELECT
                id,
                COALESCE(conversation_id, session_id) AS session_id,
                conversation_id,
                current_product,
                current_brand,
                current_article,
                current_category,
                current_doc_id,
                last_intent,
                last_answer_mode,
                last_sources_json,
                last_documents_json,
                updated_at
            FROM conversation_state_old_unique_session
            '''
        ))
        conn.execute(text('DROP TABLE conversation_state_old_unique_session'))


def _ensure_schema_upgrades() -> None:
    _rebuild_conversation_state_without_session_unique()
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table_name, columns in _SCHEMA_UPGRADES.items():
            if table_name not in table_names:
                continue
            existing = {column['name'] for column in inspector.get_columns(table_name)}
            for column_name, column_sql in columns:
                if column_name not in existing:
                    conn.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {column_sql}'))
        for stmt in _INDEX_UPGRADES:
            conn.execute(text(stmt))


def init_db() -> None:
    import app.storage.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_schema_upgrades()
