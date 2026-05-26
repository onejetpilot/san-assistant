# SAN Assistant (Server-Only Deployment)

В этом проекте поддерживается только серверный запуск.
Локальный dev-режим, `docker-compose.local.yml` и `.env.local.example` не используются.

## Production структура на сервере
- `/opt/san-assistant` — основное приложение
- `/opt/san-assistant-kb` — база знаний (`knowledge_base/*.txt`)
- `/opt/san-assistant-docs` — документы (`documents/`) и metadata (`metadata/documents.yml`)
- `/opt/san-assistant-data` — persistent data (`/data`: Chroma, SQLite, indexes, логи)

## Подготовка VPS
1. Установите Docker Engine и Docker Compose plugin.
2. Создайте директории:
   - `mkdir -p /opt/san-assistant /opt/san-assistant-kb /opt/san-assistant-docs /opt/san-assistant-data`
3. Клонируйте репозитории:
   - `git clone https://github.com/onejetpilot/san-assistant /opt/san-assistant`
   - `git clone https://github.com/onejetpilot/san-assistant-kb /opt/san-assistant-kb`
   - `git clone https://github.com/onejetpilot/san-assistant-docs /opt/san-assistant-docs`

## Настройка `.env`
В `/opt/san-assistant/.env` используйте container paths:
- `KNOWLEDGE_BASE_PATH=/kb/knowledge_base`
- `DOCUMENTS_REPO_PATH=/docs`
- `DOCUMENTS_METADATA_PATH=/docs/metadata/documents.yml`
- `CHROMA_PATH=/data/chroma`
- `DATABASE_URL=sqlite:////data/app.db`

Остальные переменные смотрите в `.env.example`.

## Docker Compose запуск
`docker-compose.prod.yml` монтирует:
- `/opt/san-assistant-kb:/kb:ro`
- `/opt/san-assistant-docs:/docs:ro`
- `/opt/san-assistant-data:/data`

Запуск:
```bash
cd /opt/san-assistant
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Проверка:
```bash
curl -f http://localhost:8000/api/health
```

## Переиндексация
RAG KB:
```bash
cd /opt/san-assistant
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend python -m app.rag.ingest --recreate
```

Documents:
```bash
cd /opt/san-assistant
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend python -m app.indexes.document_index --recreate
```

## Reverse proxy (Caddy/Nginx) и HTTPS
1. Поднимите reverse proxy на сервере.
2. Проксируйте:
   - frontend: `localhost:3000`
   - backend API: `localhost:8000`
3. Включите TLS (Let's Encrypt) на боевом домене.

## GitHub Actions deploy
Workflow `deploy.yml`:
- `cd /opt/san-assistant`
- `git pull`
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`
- smoke tests (`/api/health` + `/api/chat`)

Нужны secrets:
- `SSH_HOST`
- `SSH_USER`
- `SSH_KEY`

## GitHub Actions reindex
`reindex_knowledge.yml`:
- `cd /opt/san-assistant-kb && git pull`
- `cd /opt/san-assistant && docker compose ... exec backend python -m app.rag.ingest --recreate`

`reindex_documents.yml`:
- `cd /opt/san-assistant-docs && git pull`
- `cd /opt/san-assistant && docker compose ... exec backend python -m app.indexes.document_index --recreate`

## Systemd (опционально)
Файл: `infra/systemd/san-rag-web.service`

Установка:
```bash
sudo cp infra/systemd/san-rag-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable san-rag-web
sudo systemctl start san-rag-web
```

Логи:
```bash
sudo journalctl -u san-rag-web -f
```
