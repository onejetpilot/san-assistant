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
    'CREATE UNIQUE INDEX IF NOT EXISTS ix_conversation_state_conversation_id ON conversation_state (conversation_id)',
]


def _ensure_schema_upgrades() -> None:
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
