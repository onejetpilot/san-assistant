# CI/CD Guide (Server-Only)

## Repositories
- `onejetpilot/san-assistant`
- `onejetpilot/san-assistant-kb`
- `onejetpilot/san-assistant-docs`

## Server paths
- `/opt/san-assistant`
- `/opt/san-assistant-kb`
- `/opt/san-assistant-docs`
- `/opt/san-assistant-data`

## Required secrets (all repos)
- `SSH_HOST`
- `SSH_USER`
- `SSH_KEY`

Optional:
- `APP_BASE_URL`
- `APP_ACCESS_TOKEN`
- `ADMIN_TOKEN`

## Workflows
### san-assistant
- `.github/workflows/ci.yml`
- `.github/workflows/deploy.yml`

### san-assistant-kb (copy template)
- `ci_cd_templates/san-assistant-kb/validate_and_reindex.yml`

### san-assistant-docs (copy template)
- `ci_cd_templates/san-assistant-docs/validate_and_reindex_documents.yml`

## Server scripts
- `scripts/server_bootstrap.sh`
- `scripts/deploy_server.sh`
- `scripts/reindex_knowledge_server.sh`
- `scripts/reindex_documents_server.sh`
- `scripts/smoke_health.sh`
- `scripts/smoke_chat.sh`
- `scripts/smoke_rag.sh`
- `scripts/smoke_documents.sh`

All scripts use `set -euo pipefail` and fail fast.
