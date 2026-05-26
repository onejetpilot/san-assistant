# SAN Assistant (Server-Only Deployment)

Проект рассчитан только на server-only запуск на VPS.

## Репозитории
- `onejetpilot/san-assistant`
- `onejetpilot/san-assistant-kb`
- `onejetpilot/san-assistant-docs`

## Серверная структура
- `/opt/san-assistant`
- `/opt/san-assistant-kb`
- `/opt/san-assistant-docs`
- `/opt/san-assistant-data`

## Container paths
- `KNOWLEDGE_BASE_PATH=/kb/knowledge_base`
- `DOCUMENTS_REPO_PATH=/docs`
- `DOCUMENTS_METADATA_PATH=/docs/metadata/documents.yml`
- `CHROMA_PATH=/data/chroma`
- `DATABASE_URL=sqlite:////data/app.db`

## CI/CD
### Workflows by repository
- `san-assistant/.github/workflows/ci.yml`
- `san-assistant/.github/workflows/deploy.yml`
- `san-assistant-kb/.github/workflows/validate_and_reindex.yml` (template in this repo)
- `san-assistant-docs/.github/workflows/validate_and_reindex_documents.yml` (template in this repo)

### Required secrets
Add in each repo: `Settings -> Secrets and variables -> Actions`.

Common:
- `SSH_HOST`
- `SSH_USER`
- `SSH_KEY`

Optional:
- `APP_ACCESS_TOKEN`
- `ADMIN_TOKEN`
- `APP_BASE_URL`

### SSH deploy key
```bash
ssh-keygen -t ed25519 -C "github-actions-san-assistant" -f ~/.ssh/san_assistant_deploy
```
- private key -> GitHub Secret `SSH_KEY`
- public key -> server `~/.ssh/authorized_keys`

## Bootstrap VPS
```bash
cd /opt/san-assistant
./scripts/server_bootstrap.sh
```

Then clone repos into `/opt/*`, create `/opt/san-assistant/.env`, and run deploy.

## Deploy / Reindex
Deploy app:
```bash
cd /opt/san-assistant
./scripts/deploy_server.sh
```

Reindex KB:
```bash
cd /opt/san-assistant
./scripts/reindex_knowledge_server.sh
```

Reindex docs:
```bash
cd /opt/san-assistant
./scripts/reindex_documents_server.sh
```

## Logs
```bash
cd /opt/san-assistant
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f frontend
```

## Rollback
- Revert commit in corresponding repo (`git revert`).
- Re-run deploy or reindex workflow.
- For KB/docs issues: revert in KB/docs repo and rerun reindex workflow.

## Extra docs
- `docs/CI_CD.md`

## Frontend / Chat UI

Frontend построен на Next.js (App Router) и использует современный chat UX с компонентной архитектурой, совместимой с assistant-ui подходом (headless chat composition).

### Env
- `NEXT_PUBLIC_API_BASE_URL` — базовый URL backend API (если пусто, используется текущий origin через reverse proxy)
- `NEXT_PUBLIC_APP_NAME` — имя приложения в UI (опционально)

### Backend contract
Frontend работает только как тонкий клиент к FastAPI:
- `POST /api/chat`
- `POST /api/feedback`
- `GET /api/admin/status`
- `GET /api/health`

### Access token
- Токен хранится в `localStorage`.
- Передается как `Authorization: Bearer <token>`.
- При `401` показывается token gate.
- Есть действия: `Сменить токен` и `Выйти`.

### Session
- `session_id` хранится в `localStorage`.
- Каждый `/api/chat` отправляет `session_id`.
- Если backend вернул новый `session_id`, frontend сохраняет его.
- Кнопка `Новый чат` очищает локальную историю и сбрасывает `session_id`.

### Chat response blocks
Assistant response отображает:
- answer text
- answer_mode
- confidence
- used_web_search
- tools_used
- sources
- documents
- web results
- feedback (👍/👎)

### Key frontend files
- `frontend/app/page.tsx`
- `frontend/app/admin/page.tsx`
- `frontend/components/chat/*`
- `frontend/components/auth/TokenGate.tsx`
- `frontend/components/admin/AdminStatus.tsx`
- `frontend/lib/api.ts`
- `frontend/lib/types.ts`
- `frontend/lib/storage.ts`

