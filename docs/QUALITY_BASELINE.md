# Quality Baseline

Baseline captured before product-answer quality fixes.

## Scope

The first quality target is correct answers for SAN plumbing products. Document search is intentionally out of scope for the current iteration.

The primary golden RAG sample is:

- `/root/projects/san-assistant-kb/knowledge_base/ondo_axial_fittings_rag_ready.txt`

Production reindex should still process the full knowledge base. The golden sample is used as the first regression target because its structure is the current reference format.

## Current Check Results

Backend tests:

```text
pytest -q
7 failed, 14 passed
```

Known failing groups:

- `tests/test_router.py` - router treats ordinary words as article-like tokens before checking document, web, and offtopic intents.
- `tests/test_validator.py` - validator currently reports some malformed KB cases as warnings or ignores them, while tests expect errors.
- `tests/test_document_search.py` - document search test assumes an initialized collection; document search is not part of the current quality focus.

Backend import:

```text
DATABASE_URL=sqlite:////tmp/san-assistant-baseline.db python -c "import app.api.main"
passes
```

Local import with the project `.env` uses the production-style SQLite path `/data/app.db`. In this sandboxed inspection environment that path is not writable, so import must use a temporary SQLite URL.

Docker compose:

```text
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
not runnable in this WSL session: docker command is unavailable
```

Frontend checks:

```text
npm run typecheck
npm run build
not runnable in this WSL session: Node reports unsupported WSL environment
```

## Current Quality Risks

- Article detection is too broad and can classify normal words as articles.
- RAG can silently use zero-vector embeddings when embedding settings are missing.
- RAG results are returned without a minimum relevance threshold.
- Local `data/indexes/` is empty until reindex is run.
- Knowledge base validation reports article conflicts across the full KB; these should become a separate content backlog.

## Next Step

Fix router behavior without changing the public `/api/chat` response contract or frontend types.
