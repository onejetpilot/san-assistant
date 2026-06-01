# Architecture Review

## 1. Executive summary

Общее состояние проекта: зрелый MVP web RAG assistant с корректным разделением UI и API на уровне структуры репозитория, но с несколькими критическими пробелами для production-ready режима.

Сильные стороны:
- Ясная web-only архитектура: Next.js frontend + FastAPI backend.
- Есть единый orchestration слой (`AnswerService`) для `/api/chat`.
- Возвращается структурированный chat response (`answer`, `answer_mode`, `confidence`, `tools_used`, `sources`, `documents`, `web_results`).
- Разделены deploy и reindex процессы, есть healthcheck в prod compose.
- Есть базовый eval runner и smoke-скрипты.

Главные риски:
- Критично: backend endpoints фактически не защищены bearer token-ом (auth отсутствует в FastAPI routes).
- Нет формальной валидации/ограничения длины пользовательского сообщения и `session_id`.
- Слабая observability: нет request tracing/correlation и структурированных error envelopes.
- Возможна деградация retrieval при fallback embeddings `[0.0]*8` и отсутствии четкого threshold-правила no-answer.
- Deploy/reindex скрипты используют `git reset --hard`, что рискованно для ручных hotfix на сервере.

Уровень зрелости: **MVP (не production-ready без доработок в security/observability/error contract).**

## 2. Current architecture

Фактический поток:
User → Next.js Frontend (`frontend/components/chat/ChatLayout.tsx`) → FastAPI `POST /api/chat` (`app/api/routes_chat.py`) → `AnswerService.answer()` (`app/services/answer_service.py`) → query resolve/expand + routing (`app/services/query_resolver.py`, `app/services/router.py`) → Product Lookup (`app/indexes/sku_index.py`) / RAG (`app/rag/retriever.py`) / Documents (`app/documents/document_search.py`) / web fallback stub (`app/web_search/san_team_search.py`) → LLM client (`app/core/llm_client.py`) → structured response → frontend blocks (`AssistantMessage`, `SourcesBlock`, `DocumentsBlock`, `WebResultsBlock`).

Важное отличие от целевой практики: явный Auth/session layer как middleware/dependency в API отсутствует; токен хранится и отправляется frontend, но backend его не валидирует.

## 3. What is good

- Точки входа и роуты прозрачны: `app/api/main.py`, отдельные route-файлы.
- Есть Pydantic request/response схемы: `ChatRequest`, `ChatResponse`, `FeedbackRequest`.
- `AnswerService` можно вызывать программно без HTTP (используется в `app/evaluation/run_regression_eval.py`).
- Session/history вынесены в SQLite через `ConversationMemoryService`, а не только в frontend state.
- Есть intent routing (rules/llm/hybrid), отдельные сервисы query resolve/slots/confidence.
- Возврат sources/documents/web metadata уже machine-readable.
- Документный индекс валидирует metadata и существование файлов на этапе индексации (`app/indexes/document_index.py`).
- CI включает backend tests + frontend build + docker compose config/build.

## 4. Main problems

1. **CRITICAL: отсутствует backend auth enforcement.**
- Где видно: `app/api/routes_chat.py`, `app/api/routes_feedback.py`, `app/api/routes_admin.py` не используют security dependencies; поиск по backend не показывает `HTTPBearer`/`Depends`/token validation.
- Почему проблема: любой клиент, знающий URL, может вызывать `/api/chat`, `/api/feedback`, `/api/admin/status`.
- Риск: открытый внутренний ассистент, утечки operational данных, злоупотребление API.

2. **PROBLEM: API валидация входа недостаточна.**
- Где видно: `app/core/schemas.py` (`message: str` без `min_length/max_length`, `session_id` без формата).
- Почему проблема: нет защиты от слишком длинных запросов, мусорных session id, возможной перегрузки LLM/context.
- Риск: нестабильность latency/cost, неожиданные ошибки.

3. **PROBLEM: error handling не унифицирован как стабильный API contract.**
- Где видно: исключения в route-функциях не оборачиваются в единый error schema; `feedback`/`admin` возвращают ad-hoc JSON.
- Почему проблема: frontend вынужден опираться на текст/статус, а не на типизированные коды/поля ошибок.
- Риск: contract drift и сложная диагностика.

4. **PROBLEM: observability минимальная.**
- Где видно: нет request_id trace на уровне FastAPI middleware; `app/core/logging.py` почти не используется; нет child spans routing/retrieval/llm.
- Почему проблема: трудно объяснить, почему выбран маршрут/ответ.
- Риск: медленная отладка инцидентов, сложно контролировать качество.

5. **PARTIAL/PROBLEM: retrieval/no-answer политика не строго формализована.**
- Где видно: `RagRetriever` возвращает `score=1-dist`; строгого порога фильтрации chunks нет, confidence heuristic в `app/services/confidence.py`.
- Почему проблема: слабые совпадения могут попадать в контекст; no-answer поведение не полностью детерминировано.
- Риск: hallucination/неточные ответы.

## 5. Comparison with common web RAG assistant practices

- frontend/backend separation: **OK**
  - Frontend в целом thin client, orchestration в backend.
- API contract: **PARTIAL**
  - Есть схемы и structured response, но нет формального error schema и входных ограничений.
- auth/session: **CRITICAL**
  - Session есть, auth enforcement на backend нет.
- RAG pipeline: **PARTIAL**
  - Есть Chroma + metadata + chunking, но threshold/rerank (по умолчанию off) и rejection-policy слабые.
- product lookup: **PARTIAL**
  - Есть отдельный SKU/kit индекс, но ограничен exact article lookup без полноценного fuzzy/alias pipeline.
- documents search: **PARTIAL**
  - Индексация metadata валидируется хорошо; runtime fallback есть, но runtime file existence check неявный.
- routing: **PARTIAL**
  - Есть deterministic rules + hybrid; no structured route telemetry per request.
- prompting: **PARTIAL**
  - Prompt централизован, но нет versioning/logging prompt revision.
- LLM client: **PARTIAL**
  - Централизован, timeout есть; нет retry/backoff/fallback model и нормализованных error классов.
- observability: **PROBLEM**
  - Нет единого root trace/request correlation на `/api/chat`.
- error handling: **PROBLEM**
  - Нет единого machine-readable error envelope.
- config/secrets: **PARTIAL**
  - Конфиг централизован, но обязательные секреты не валидируются на старте.
- deployment: **PARTIAL**
  - Persistent `/data` и healthcheck есть, но deploy scripts агрессивны (`reset --hard`).
- evaluation: **PARTIAL**
  - Есть regression runner, но нет автоматизированного VPS eval workflow и baseline-отчетов.
- security: **CRITICAL**
  - Из-за отсутствия backend auth; плюс localStorage token (MVP допустимо, но риск XSS нужно явно фиксировать).

## 6. Recommendations

### Quick wins

- Добавить backend token validation dependency для `/api/chat`, `/api/feedback`, `/api/admin/*` (с разделением app/admin token).
- Ввести ограничения в `ChatRequest` (`message` min/max length, формат `session_id`).
- Ввести единый error response schema (`code`, `message`, `request_id`, `details`).
- Добавить startup validation обязательных env (LLM key, DB path, CHROMA path, токены если auth включен).
- Добавить middleware request_id и логирование route + latency + tools_used + intent.

### Medium improvements

- Ввести retrieval threshold policy и явное `not_enough_data` при слабом evidence.
- Добавить bounded history policy (token/window cap, summarization strategy).
- Добавить retry/backoff и fallback model policy в LLM client.
- Стабилизировать API contract в отдельном backend schema doc + frontend contract test.
- Разделить admin operational endpoints по отдельной auth policy и audit logs.

### Later / strategic improvements

- Вынести orchestrator/router/retrieval observability в полноценный tracing (OpenTelemetry/Langfuse).
- Ввести комбинированный product lookup (exact + fuzzy + alias + semantic rank).
- Добавить offline evaluation pipeline (категории вопросов, baseline JSON/Markdown отчеты, regression gates).
- Вынести prompt management/versioning в управляемый слой.
- Продумать migration с localStorage token на более безопасный session/cookie подход (если модель угроз усилится).

## 7. Suggested target architecture

```text
backend/
  app/
    api/
      main.py
      routes_chat.py
      routes_feedback.py
      routes_admin.py
      routes_health.py
      schemas.py
      errors.py
      auth.py
    agent/
      orchestrator.py
      router.py
      prompts.py
    retrieval/
      rag_search.py
      product_lookup.py
      documents_search.py
      chroma_client.py
    llm/
      client.py
    session/
      memory.py
      history_policy.py
    observability/
      tracing.py
      logging.py
      sanitize.py
    evaluation/
      run_rag_eval.py
      questions.py
    config.py

frontend/
  app/
    page.tsx
    admin/page.tsx
  components/
    chat/
    auth/
    admin/
  lib/
    api.ts
    types.ts
    storage.ts
```

## 8. Risk matrix

- hallucinations
  - severity: high
  - likelihood: medium
  - mitigation: retrieval threshold + no-answer policy + stricter context filtering.

- wrong product match
  - severity: high
  - likelihood: medium
  - mitigation: product disambiguation flow, fuzzy+exact hybrid lookup, explicit clarification question.

- no answer when answer exists
  - severity: medium
  - likelihood: medium
  - mitigation: query rewrite tuning, reranker enablement, eval coverage for recall cases.

- fallback overuse
  - severity: medium
  - likelihood: low (сейчас web fallback фактически stub)
  - mitigation: explicit fallback triggers + telemetry.

- frontend/backend contract drift
  - severity: medium
  - likelihood: medium
  - mitigation: shared schema checks + contract tests.

- broken auth
  - severity: high
  - likelihood: high
  - mitigation: mandatory backend bearer validation + admin token split.

- token leakage
  - severity: high
  - likelihood: medium
  - mitigation: sanitize logs, never log Authorization, XSS hardening, CSP.

- LLM API outage
  - severity: medium
  - likelihood: medium
  - mitigation: retries/backoff/fallback model + graceful degraded responses.

- ChromaDB missing/corrupted collection
  - severity: high
  - likelihood: medium
  - mitigation: startup checks, index version checks, health endpoint enrichment.

- SQLite/session issues
  - severity: medium
  - likelihood: medium
  - mitigation: DB health checks, backup policy, bounded message history.

- documents metadata mismatch
  - severity: medium
  - likelihood: low
  - mitigation: keep strict validate step before reindex (already present), add runtime warning telemetry.

- poor observability
  - severity: high
  - likelihood: high
  - mitigation: request_id tracing + structured event logs for routing/retrieval/llm.

- hard-to-test architecture
  - severity: medium
  - likelihood: medium
  - mitigation: add API smoke/eval automation and deterministic fixtures.

- deploy accidentally overwrites data
  - severity: high
  - likelihood: medium
  - mitigation: backup `/opt/san-assistant-data`, safer deploy script, rollback automation.

## 9. Concrete next steps

1. Проверить и зафиксировать стабильность `/api/health` и `/api/chat` на VPS smoke-тестами после каждого deploy.
2. Формально зафиксировать API contract backend/frontend (включая errors) и проверить соответствие типов.
3. Внедрить backend auth enforcement для app/admin endpoints и явно проверить 401/403 сценарии.
4. Добавить валидацию `session_id` и лимит длины `message` в `ChatRequest`.
5. Уточнить retrieval threshold/no-answer политику и покрыть ее регрессионными вопросами.
6. Расширить eval runner: сохранять результаты в JSON/Markdown и группировать по категориям вопросов.
7. Добавить GitHub Actions workflow для запуска eval на VPS через SSH после deploy.
8. Внедрить request-level observability (request_id, route reason, tools_used, top_k, model, latency).
9. Укрепить documents/product lookup: disambiguation и richer matching rules.

