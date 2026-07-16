# Testing DocuQuery AI

DocuQuery AI tests are designed to run without real OpenAI, Gemini, or other
paid LLM provider calls. Tests use fake RAG pipelines, mocked provider clients,
deterministic embeddings, and mocked frontend API responses.

## Backend Tests

Run from the project root with Docker Compose services:

```bash
docker compose up -d postgres qdrant
docker compose exec -T backend python -m unittest discover -s tests -v
```

Or run inside a backend container/image with test environment variables:

```bash
cd backend
python -m unittest discover -s tests -v
```

Backend test categories:

- Authentication and role separation: signed sessions, invalid tokens, admin
  password failures, login rate limits, and production credential validation.
- API route behavior: chat defaults, admin-only document routes, evaluation,
  optimization, feedback, analytics, and clean error responses.
- Document and RAG units: PDF validation/loading, chunking, indexing orchestration,
  citation/source formatting, and no-context refusal behavior.
- Evaluation and optimization services: official CSV validation, deterministic
  quality metrics, bounded optimization search, cancellation, and apply-best.
- Provider configuration: OpenAI-compatible provider presets, custom base URLs,
  legacy `OPENAI_API_KEY` compatibility, and separate chat/embedding providers.

## Frontend Tests

```bash
cd frontend
npm install
npm test -- --run
npm run build
```

Frontend test categories:

- Route guards and role UI: anonymous redirects, user/admin visibility, and
  admin-only pages.
- Chat UI: mocked answers, citations, default settings, and feedback actions.
- Admin pages: document management, evaluation metrics, optimization progress,
  analytics, and loading/error states.
- Legal/privacy UI: Terms, Privacy, Cookie/Storage Policy, acceptance gate,
  footer links, and consent preferences.

## CI

GitHub Actions workflow: `.github/workflows/ci.yml`.

CI runs on push and pull request:

- Backend tests with PostgreSQL and Qdrant service containers.
- Frontend tests.
- Frontend production build.

CI sets fake provider keys such as `LLM_API_KEY=test-key-not-real` and does not
call real LLM APIs. Live provider validation should be a separate, opt-in smoke
test run only when a real key is intentionally provided.
