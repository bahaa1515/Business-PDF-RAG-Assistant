# DocuQuery AI Test Coverage Audit

Date: 2026-06-14

Scope: Phase 1 audit only. No production behavior or test behavior was changed as
part of this report.

## Executive Summary

The current automated suite is useful and green, but it does not yet prove that
DocuQuery AI is production-ready.

Update on 2026-06-16: multi-provider AI configuration tests were added after
this original audit. The backend now has focused tests for OpenAI-compatible
provider resolution, legacy `OPENAI_API_KEY` compatibility, custom base URLs,
separate chat/embedding providers, and provider-specific keys such as
`GROQ_API_KEY`. These tests improve configuration coverage, but they do not
replace paid live integration tests against each provider/model.

Update on 2026-06-16: a GitHub Actions workflow was added at
`.github/workflows/ci.yml` for backend tests, frontend tests, and frontend
build. Additional security scans, Playwright E2E, and deployment gates are
still future hardening work.

| Area | Current Baseline |
| --- | --- |
| Backend tests | 32 passed, 0 failed, 0 skipped |
| Backend line coverage | 80% (1,299 statements, 259 missing) |
| Frontend tests | 18 passed across 12 files, 0 failed |
| Frontend statements/lines | 87.9% |
| Frontend branches | 68.72% |
| Frontend functions | 57.57% |
| Real PostgreSQL integration tests | None |
| Real Qdrant integration tests | One smoke test, mixed into the fast suite and skipped if Qdrant is unavailable |
| Real configured-AI-provider integration tests | None |
| Real backend/frontend E2E tests | None |
| Playwright tests | None |
| CI pipeline | Present for backend tests, frontend tests, and frontend build |
| Automated security scans | None found |

Coverage percentages describe which lines executed. They do not prove that
authorization is complete, that the browser and backend work together, or that
the real RAG stack returns grounded answers. Most API tests patch the service
layer, and all frontend feature tests mock the API.

### Commands Used For This Baseline

Backend:

```bash
docker compose exec -T backend pip install -r requirements-dev.txt
docker compose exec -T backend coverage run -m unittest discover -s tests
docker compose exec -T backend coverage report -m
```

Result: 32 tests passed. Backend line coverage: 80%.

Frontend:

```bash
docker compose run --rm frontend npm run test:coverage
```

Result: 18 tests passed. Frontend statements/lines: 87.9%, branches:
68.72%, functions: 57.57%.

Warnings observed:

- Backend tests use an `httpx` application shortcut that is deprecated.
- Frontend tests emit React Router v7 future-flag warnings.

## Test Category Summary

| Category | Present? | Assessment |
| --- | --- | --- |
| Backend unit tests | Yes | Good initial coverage of helpers, metrics, validation, and orchestration |
| Backend service tests | Yes | Mostly SQLite plus fake RAG/vector/document services |
| Backend API tests | Yes | FastAPI `TestClient`, but database and service layers are mocked |
| Backend authorization matrix | Partial | A few role checks exist; most endpoints lack anonymous/user/admin matrix coverage |
| Real service integration | Partial | One Qdrant smoke test; no real PostgreSQL workflow test |
| RAG correctness | Partial | Pipeline formatting/refusal uses fake retrieval and generation |
| Frontend component tests | Yes | Good user-visible component coverage with mocked APIs |
| Frontend route tests | Partial | Route guard is tested for one admin route with mocked role state |
| Browser E2E | No | No real browser-to-backend workflow is automated |
| Production environment safety | No | No tests for unsafe secrets, default admin password, CORS, or public service exposure |
| Security automation | No | No dependency, secret, static analysis, or dynamic security scans found |

## Existing Backend Tests

### `backend/tests/test_api_endpoints.py`

All tests use FastAPI `TestClient`. The database dependency is replaced with a
`MagicMock`, and endpoint services are patched. These tests prove routing,
dependency use, request parsing, and selected endpoint decisions. They do not
prove real database, filesystem, Qdrant, configured AI provider, or
cross-service behavior.

| Test | Type | What It Verifies | Production Risk Protected | What It Does Not Prove |
| --- | --- | --- | --- | --- |
| `test_auth_login_me_and_admin_rejection` | API with mocked DB | User login succeeds, `/auth/me` returns a user role, and a wrong admin password returns 401 | Basic login and role response regressions | Missing/malformed/tampered tokens, admin success, login rate limiting, production secret safety |
| `test_health_reports_healthy_and_degraded` | API with mocked dependencies | Health is healthy when mocked DB/Qdrant checks pass and degraded when Qdrant fails | Incorrect health status mapping | Real PostgreSQL/Qdrant connectivity or exception behavior |
| `test_chat_enforces_user_defaults_and_returns_structured_error` | API with mocked chat service | User-supplied admin settings are replaced with safe defaults; provider failure returns a structured 502 | Normal users forcing debug/retrieval settings; raw provider errors reaching clients | Real RAG behavior, anonymous rejection, rate limiting, long/invalid questions |
| `test_chat_admin_validation_history_and_clear` | API with mocked chat service | Admin `top_k=999` is rejected; admin history includes all sessions; admin can clear history | Unsafe admin `top_k`; accidental loss of admin history capability | Admin chat success, user history isolation at API level, anonymous/user clear-history rejection |
| `test_document_endpoints` | API with mocked document service | User cannot list documents; admin upload rejects `.txt`; admin can upload/list/preview/reindex/reset; missing delete returns 404 | One role check, extension filtering, route wiring | Anonymous/user denial for each endpoint, successful real deletion/upload/indexing, PDF safety |
| `test_feedback_and_analytics_endpoints` | API with mocked feedback service | User can submit feedback and admin can read analytics | Broken endpoint contracts | Feedback ownership, anonymous rejection, user analytics rejection, real persisted analytics |
| `test_evaluation_endpoint` | API with mocked evaluation service | Admin can run evaluation; non-CSV extension is rejected | Basic evaluation route contract and extension check | Authorization matrix, CSV content validation, real evaluation/indexing |
| `test_optimization_endpoints` | API with mocked evaluation/job services | Admin can start/read/cancel an optimization job and apply a result | Basic optimization route contract | Authorization matrix, rate limits, real job lifecycle, failure cleanup, valid completed-run enforcement |

### `backend/tests/test_portfolio_requirements.py`

| Test | Type | What It Verifies | Production Risk Protected | What It Does Not Prove |
| --- | --- | --- | --- | --- |
| `test_quality_metrics_are_deterministic_and_explained` | Unit | Deterministic correctness, faithfulness, relevance, and explanation output | Metric regressions and unexplained scoring | Semantic quality against real model answers |
| `test_duplicate_original_filenames_get_unique_stored_filenames` | Filesystem integration | Two uploads with the same original name receive unique stored names and preserve bytes | File overwrite/data-loss risk | Concurrent uploads, database records, full PDF validity |
| `test_pdf_upload_rejects_non_pdf_content` | Unit/filesystem | A `.pdf` containing plain text is rejected by the file utility | Basic fake-PDF upload risk | Sophisticated malformed PDF, empty/scanned PDF handling, endpoint behavior |
| `test_auth_token_contains_session_and_expiration_is_enforced` | Unit | Token contains role/session and expired tokens are rejected | Expired session reuse | API-level missing/malformed/tampered token handling, unsafe secrets |
| `test_chat_history_is_isolated_by_session_and_errors_are_not_answers` | Service integration with SQLite and fake RAG | Service history filters by session and failed RAG calls are not saved as answers | Cross-session data exposure in service logic; storing failed answers | API authorization, admin behavior, real PostgreSQL concurrency |
| `test_document_original_filename_is_used_for_display` | Model/SQLite integration | Original filename is retained separately from stored filename | Leaking opaque stored names to users | API display behavior or filesystem safety |
| `test_feedback_and_failed_question_analytics` | Service integration with SQLite | Feedback is created and several failed-question categories are populated | Analytics classification regressions | API authorization and real PostgreSQL behavior |
| `test_rate_limiter_rejects_requests_over_limit` | Unit | In-memory limiter returns 429 after its limit | Basic request-flood control logic | Login rate limiting, endpoint wiring, multiple processes, Redis/distributed limits |
| `test_hybrid_combines_vector_and_keyword_results_and_reranks` | Unit with fake vector store | Hybrid retrieval fuses semantic/keyword results and reranks | Retrieval ordering regressions | Real embeddings, Qdrant results, citation correctness |
| `test_temporary_collection_upsert_and_search` | Real Qdrant smoke integration | A temporary collection can be created, written, searched, and deleted | Basic Qdrant client compatibility | Application collection workflows, PostgreSQL coordination, delete/reset/reindex behavior; skips if unavailable |

### `backend/tests/test_evaluation_service.py`

These tests use in-memory SQLite, a fake document service, and a fake RAG
pipeline.

| Test | Type | What It Verifies | Production Risk Protected | What It Does Not Prove |
| --- | --- | --- | --- | --- |
| `test_evaluation_returns_complete_metrics` | Service integration with fakes | Evaluation persists and returns all expected metrics and per-question output | Missing/incorrect evaluation result fields | Real retrieval, generation, indexing, PostgreSQL |
| `test_optimization_indexes_once_per_configuration_and_exports_ranking` | Service integration with fakes/filesystem | Each configuration indexes once, results are ranked/exported, and previous configuration is restored | Excess reindexing, missing export, lost prior config | Real Qdrant/configured-provider cost, failure recovery, concurrency |
| `test_csv_requires_reference_answer_only_for_answerable_questions` | Service validation | Valid answerable/unanswerable rows load; answerable row without reference answer fails | Invalid labeled evaluation data | All required-column/row edge cases, size/row limits |
| `test_apply_best_configuration_rebuilds_active_index` | Service integration with fakes | Best ranked configuration triggers an index rebuild | Apply-best failing to update index | Completed/failed/cancelled run validation, real Qdrant |
| `test_optimization_with_no_previous_index_resets_after_run` | Service integration with fakes | Optimization resets the index when no prior active configuration exists | Leaving an unintended active experimental index | Real reset behavior and failure handling |
| `test_invalid_overlap_combination_is_rejected` | Service validation | `chunk_overlap >= chunk_size` is rejected | Invalid chunk configuration | API-level validation and other invalid values |
| `test_optimization_safety_limits_top_k_and_configuration_count` | Service validation | Excessive `top_k` and too many configurations are rejected | Unbounded optimization API cost | Concurrent jobs, CSV size, total question/call budget |

### `backend/tests/test_optimization_jobs.py`

These tests use fake sessions and fake evaluation services. They exercise the
in-memory thread/job coordinator only.

| Test | Type | What It Verifies | Production Risk Protected | What It Does Not Prove |
| --- | --- | --- | --- | --- |
| `test_background_job_reports_progress_and_result` | Unit/concurrency with fakes | Job reaches completed status, reports progress/result, and closes its session | Lost progress/result and leaked session | Real optimization, process restart, multi-worker behavior, persisted jobs |
| `test_background_job_can_be_cancelled` | Unit/concurrency with fakes | Cancellation request produces cancelled status and closes its session | Cancellation signal ignored | Real index restoration, partial result safety, apply-best restrictions |

### `backend/tests/test_document_and_rag.py`

| Test | Type | What It Verifies | Production Risk Protected | What It Does Not Prove |
| --- | --- | --- | --- | --- |
| `test_chunker_preserves_page_metadata_and_overlap` | Unit | Chunking produces multiple ordered chunks with the source page preserved | Lost page metadata/citation basis | Retrieval accuracy across real PDFs |
| `test_pdf_loader_reads_pdf_and_rejects_invalid_file` | Component/filesystem | A generated PDF can be read and invalid bytes fail validation | Loader incompatibility and invalid PDF handling | Empty/scanned/encrypted/oversized PDFs |
| `test_rag_pipeline_refuses_without_chunks_and_formats_debug_sources` | Unit with fake retriever/generator | No chunks produces refusal; answer/source/debug fields are formatted | Missing refusal and broken source metadata formatting | Grounded model answer, injection resistance, unrelated source exclusion |
| `test_document_service_indexes_and_resets_documents` | Service integration with SQLite/fakes | Indexing updates document status/metadata and reset returns it to uploaded | Lost source filename/configuration and reset status regressions | Real provider embeddings, Qdrant writes/clears, multi-document failure behavior |
| `test_document_upload_cleans_saved_file_when_pdf_loading_fails` | Unit with mocks | A saved file is deleted if PDF loading fails | Orphaned files after failed upload | Actual filesystem cleanup, endpoint response, DB rollback with PostgreSQL |

## Existing Frontend Tests

All existing frontend tests run in Vitest/JSDOM. API calls and authentication
state are mocked. They are component or route tests, not E2E tests.

### `frontend/src/App.test.jsx`

| Test | Type | What It Verifies | What It Does Not Prove |
| --- | --- | --- | --- |
| `redirects anonymous visitors to login` | Route test with mocked auth/pages | Anonymous role state renders the login route | Real token restoration, browser navigation, backend 401 |
| `blocks normal users from admin routes` | Route test with mocked auth/pages | A user role opening `/analytics` sees Unauthorized | All admin routes, backend enforcement, modified localStorage behavior |
| `allows admins to open analytics` | Route test with mocked auth/pages | Admin role can render the analytics route | Real admin token/API authorization |

### `frontend/src/contexts/RoleContext.test.jsx`

| Test | Type | What It Verifies | What It Does Not Prove |
| --- | --- | --- | --- |
| `restores an existing session` | Component/context with mocked API | Stored token plus successful mocked `/auth/me` restores admin role | Invalid/expired token cleanup, real backend |
| `logs in, stores the token, and logs out` | Component/context with mocked API | Login stores token; logout removes it and clears role | Backend logout/revocation, redirect after logout, localStorage security |

### `frontend/src/components/Layout.test.jsx`

| Test | Type | What It Verifies | What It Does Not Prove |
| --- | --- | --- | --- |
| `shows only chat navigation for normal users` | Component with mocked role | User navigation hides Documents and Failed Questions | Direct URL/API access control |
| `shows all admin navigation and logs out` | Component with mocked role | Admin links render and Logout calls the context function | Real protected navigation or session invalidation |

### `frontend/src/pages/LoginPage.test.jsx`

| Test | Type | What It Verifies | What It Does Not Prove |
| --- | --- | --- | --- |
| `logs in as a normal user without a password` | Component with mocked auth | User button calls login with the expected values | Real login response/error |
| `requires and submits the admin password` | Component with mocked auth | Empty admin password disables button; entered password is submitted | Wrong-password error, login rate limiting, real backend |

### `frontend/src/pages/ChatPage.test.jsx`

| Test | Type | What It Verifies | What It Does Not Prove |
| --- | --- | --- | --- |
| `asks a question using user defaults and stores feedback` | Component with mocked API | User question sends default settings, renders answer, and submits helpful feedback | Real answer/citation rendering against backend, error/loading/rate-limit states |

### `frontend/src/pages/DocumentsPage.test.jsx`

| Test | Type | What It Verifies | What It Does Not Prove |
| --- | --- | --- | --- |
| `loads documents and supports preview, reindex, reset, and delete` | Component with mocked API | Main document actions call the expected API functions and preview renders | Actual upload/index/delete/reset behavior, authorization, error states |

### `frontend/src/pages/EvaluationPage.test.jsx`

| Test | Type | What It Verifies | What It Does Not Prove |
| --- | --- | --- | --- |
| `runs a labeled evaluation and renders quality metrics` | Component with mocked API | CSV selection triggers evaluation and metrics/results render | CSV validation, real evaluation, error/loading behavior |

### `frontend/src/pages/OptimizationPage.test.jsx`

| Test | Type | What It Verifies | What It Does Not Prove |
| --- | --- | --- | --- |
| `starts a background job, renders results, and applies the best configuration` | Component with mocked API/timer polling | Optimization starts, completed results render, and apply-best is called | Real progress/cancel/failure, job safety, actual index update |

### `frontend/src/pages/AnalyticsPage.test.jsx`

| Test | Type | What It Verifies | What It Does Not Prove |
| --- | --- | --- | --- |
| `renders failed-question categories and records` | Component with mocked API | Analytics categories and a bad-feedback record render | Real analytics data/authorization |
| `shows a clean loading error` | Component with mocked API | Rejected request renders a clean error | 401/403 session handling and real network behavior |

### `frontend/src/components/UploadPanel.test.jsx`

| Test | Type | What It Verifies | What It Does Not Prove |
| --- | --- | --- | --- |
| `selects PDFs and uploads them` | Component | Selected file is passed to the upload callback and selection clears | File validation, real multipart upload, failure handling |

### `frontend/src/components/SettingsPanel.test.jsx`

| Test | Type | What It Verifies | What It Does Not Prove |
| --- | --- | --- | --- |
| `exposes hybrid retrieval and reranking controls` | Component | Admin-style retrieval controls render and update state | Controls are hidden from users or honored safely by backend |

### `frontend/src/components/CSVFormatHelp.test.jsx`

| Test | Type | What It Verifies | What It Does Not Prove |
| --- | --- | --- | --- |
| `documents the reference answer format and downloads a sample` | Component | Help text renders and sample CSV download is initiated | Downloaded CSV works against the real evaluation endpoint |

## Endpoint Authorization Matrix

Legend:

- Yes: an existing test explicitly exercises this role/outcome.
- Partial: the role is exercised only for a failure or only indirectly.
- No: no existing test proves it.
- N/A: role-specific bearer authorization does not apply.

This matrix describes current tests, not just current implementation.

| Method | Endpoint | Required Role | Anonymous Tested? | User Tested? | Admin Tested? | Success Tested? | Failure Tested? | Existing Test File |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GET | `/` | Public | No | No | No | No | No | None |
| GET | `/health` | Public | Yes | No | No | Yes | Yes, degraded only | `test_api_endpoints.py` |
| POST | `/auth/login` | Public | Yes | Yes, user login | Partial, wrong password only | Yes, user only | Yes, wrong admin password | `test_api_endpoints.py` |
| GET | `/auth/me` | Authenticated | No | Yes | No | Yes, user only | No | `test_api_endpoints.py` |
| POST | `/chat/` | Authenticated user or admin | No | Yes | Partial, invalid `top_k` only | Yes, user only | Yes, provider failure and admin validation | `test_api_endpoints.py` |
| GET | `/chat/history` | Authenticated; user own session, admin all | No | No | Yes | Yes, admin only | No | `test_api_endpoints.py` |
| DELETE | `/chat/history` | Admin | No | No | Yes | Yes | No | `test_api_endpoints.py` |
| POST | `/feedback` | Authenticated user or admin | No | Yes | No | Yes, user only | No | `test_api_endpoints.py` |
| GET | `/analytics/failed-questions` | Admin | No | No | Yes | Yes | No | `test_api_endpoints.py` |
| GET | `/documents/` | Admin | No | Yes, rejected | Yes | Yes, admin | Yes, user 403 | `test_api_endpoints.py` |
| POST | `/documents/upload` | Admin | No | No | Yes | Yes, mocked | Yes, bad extension | `test_api_endpoints.py` |
| GET | `/documents/{document_id}/preview` | Admin | No | No | Yes | Yes, mocked | No | `test_api_endpoints.py` |
| DELETE | `/documents/{document_id}` | Admin | No | No | Yes | No | Yes, mocked not-found | `test_api_endpoints.py` |
| POST | `/documents/reindex` | Admin | No | No | Yes | Yes, mocked | No | `test_api_endpoints.py` |
| POST | `/documents/reset-index` | Admin | No | No | Yes | Yes, mocked | No | `test_api_endpoints.py` |
| POST | `/evaluation/run` | Admin | No | No | Yes | Yes, mocked | Yes, bad extension | `test_api_endpoints.py` |
| POST | `/optimization/run` | Admin | No | No | Yes | Yes, mocked | No | `test_api_endpoints.py` |
| GET | `/optimization/jobs/{job_id}` | Admin | No | No | Yes | Yes, mocked | No | `test_api_endpoints.py` |
| POST | `/optimization/jobs/{job_id}/cancel` | Admin | No | No | Yes | Yes, mocked | No | `test_api_endpoints.py` |
| POST | `/optimization/runs/{run_id}/apply-best` | Admin | No | No | Yes | Yes, mocked | No | `test_api_endpoints.py` |
| GET/HEAD | `/openapi.json` | Public by current FastAPI configuration | No | No | No | No | No | None |
| GET/HEAD | `/docs` | Public by current FastAPI configuration | No | No | No | No | No | None |
| GET/HEAD | `/docs/oauth2-redirect` | Public by current FastAPI configuration | No | No | No | No | No | None |
| GET/HEAD | `/redoc` | Public by current FastAPI configuration | No | No | No | No | No | None |

### Authorization Matrix Conclusions

- No protected endpoint has a complete anonymous/user/admin matrix.
- Only `/documents/` explicitly tests normal-user rejection.
- No endpoint explicitly tests rejection of a missing token.
- No endpoint explicitly tests malformed, tampered, expired, or invalid-role tokens.
- Admin success is not tested for `/chat/`, `/auth/me`, or `/feedback`.
- User success and session isolation are not tested through `/chat/history`.
- User rejection is not tested for any admin endpoint except `/documents/`.
- Public API documentation endpoints are enabled and untested as a production
  configuration decision.

## Observed Production Risks Requiring Tests

These are audit findings, not fixes made during Phase 1.

### Authentication And Environment Safety

- `AUTH_SECRET_KEY` defaults to `change-this-development-secret`.
- `ADMIN_PASSWORD` defaults to `admin`.
- There is no production/development environment mode or startup validation.
- Admin login is not rate-limited.
- Tokens are stored in browser `localStorage`.
- Authentication is a custom signed token model with no server-side
  revocation/logout state.

### Authorization And Data Isolation

- Backend dependencies generally enforce roles, but the full endpoint matrix is
  untested.
- Admin chat history intentionally includes all sessions; user-own-history
  isolation is tested only at service level.
- Feedback ownership and admin cross-session behavior are not API-tested.

### Input And Error Safety

- Chat questions have no explicit maximum length.
- Pydantic models do not explicitly reject unexpected extra fields.
- Evaluation/optimization CSV uploads have no explicit byte-size or row-count
  bound.
- Some endpoints return `str(exception)` to clients, which can leak internal
  implementation details.
- PDF upload has a 50 MB utility limit and a magic-header check, but important
  malformed, empty, scanned, encrypted, and partial-failure cases are untested.

### RAG And Data Consistency

- No automated test proves real provider embeddings or answer generation.
- No automated test proves a real uploaded PDF can be indexed and retrieved
  through Qdrant end to end.
- Delete/reset/reindex consistency across filesystem, PostgreSQL, and Qdrant is
  not integration-tested.
- Prompt injection, wrong-source traps, similar-document traps, and unrelated
  citation exclusion are not tested.

### Optimization Safety

- Jobs and rate limits are in memory and do not survive restart or coordinate
  across multiple workers.
- No concurrent-job limit is tested or implemented.
- `apply_best_configuration` accepts any run with result rows; there is no
  persisted completed/cancelled/failed run status to validate.
- Failed/cancelled real optimization index restoration is not integration-tested.

### Deployment And Security Automation

- PostgreSQL and Qdrant ports are exposed to the host in the current Compose
  file.
- Qdrant has no required API key in the current default Compose configuration.
- No CI workflow, Playwright suite, dependency audit, secret scan, static
  analysis, or OWASP ZAP configuration was found.
- Database schema changes use startup `create_all` and additive SQL rather than
  versioned migrations.

## Missing Production Tests

### P0: Critical Before Production

#### Authentication And Production Startup

- API tests for missing, malformed, tampered, expired, invalid-role, and
  invalid-session tokens.
- `/auth/me` tests for anonymous, user, and admin roles.
- Admin login success, wrong-password failure, and repeated-failure rate limit.
- Production startup tests that reject unsafe/default/empty
  `AUTH_SECRET_KEY` and `ADMIN_PASSWORD`.
- Development startup test that explicitly permits intentional demo defaults.
- Browser/API test proving localStorage role manipulation cannot gain backend
  admin access.

#### Full Backend Authorization Matrix

- Anonymous, user, and admin checks for every protected endpoint.
- User and admin success checks for chat where intended.
- User attempts to force `show_debug`, retrieval method, reranker, unsafe
  `top_k`, or unexpected admin-only fields.
- User-own-history API test, cross-session history denial, explicit admin
  history behavior, and user denial for global clear.
- Feedback ownership, admin behavior, anonymous denial, and user denial for
  analytics.

#### Critical API Validation And Safe Failures

- Empty and oversized chat questions; invalid retrieval/reranker/top-k/boolean
  payloads; unexpected fields.
- Non-PDF, fake PDF, empty PDF, no-text/scanned PDF, oversized PDF, and clear
  upload errors.
- Real upload rollback and cleanup tests.
- Real delete consistency across database, file, and Qdrant.
- Complete CSV validation: missing columns, empty CSV, invalid question type,
  every missing answerable field, invalid unanswerable fields, bad page, and
  bounded file/row count.
- Complete optimization validation: empty lists, non-integers, unsupported
  methods/rerankers, invalid overlaps, call/configuration bounds, and rate limit.
- Safe production error-response tests that do not expose exception details.

#### RAG Correctness And Real Integration

- Deterministic fixture tests for grounded answers, correct filename/page,
  unrelated-source exclusion, refusal, prompt injection, typo/synonym queries,
  wrong-source traps, and similar-document traps.
- Integration tests using real PostgreSQL and Qdrant for upload, reindex,
  retrieval, delete, reset, evaluation, optimization persistence, and
  apply-best.
- Tests proving deleted/reset documents cannot be retrieved and reindex restores
  retrieval.
- Separate integration test group with deterministic setup/cleanup.

#### Real Browser E2E

- Playwright user flow against the real backend: login, chat, citation,
  feedback, and direct admin URL denial.
- Playwright admin document flow: login, upload, preview, reindex, chat, delete,
  and reset.
- Playwright evaluation and bounded optimization flows.
- Session protection: logout, protected URL, invalid/expired token cleanup.

### P1: Important

- Frontend tests for wrong admin password, invalid/expired token cleanup,
  redirect after logout, API 401/403 behavior, and loading/error states.
- Frontend tests proving user/admin visibility of retrieval/debug controls.
- Frontend user-visible tests for citations, negative feedback, upload errors,
  evaluation errors, optimization progress/cancel/failure, and analytics errors.
- Real health tests for healthy, degraded, and dependency-exception cases.
- PostgreSQL migration/startup tests and a versioned migration strategy.
- Optimization failure/cancellation cleanup, concurrency limit, restart
  behavior, and completed-run-only apply-best validation.
- CI for backend tests/coverage, frontend tests/build, integration tests, and
  E2E tests.
- Dependency vulnerability scanning, secret scanning, and static analysis.
- Production CORS tests and production Compose/network exposure checks.
- Test commands that clearly separate unit, integration, and E2E suites.

### P2: Nice To Have

- Load tests for chat, upload, evaluation, and rate limiting.
- Accessibility tests and keyboard-navigation E2E.
- Cross-browser and responsive E2E coverage.
- Visual regression tests for portfolio/demo-critical pages.
- Recovery tests for PostgreSQL/Qdrant/AI-provider outages during active operations.
- Cost-budget tests and per-operation API usage accounting.
- Observability tests for structured logs, request IDs, metrics, and alerts.
- Backup/restore and disaster-recovery tests.
- Optional OWASP ZAP baseline scan against a staging deployment.

## Phase 1 Conclusion

Current status: **Not production-ready yet**.

The project has a strong demo-oriented automated test base with good line
coverage and useful service/component tests. The critical remaining problem is
proof depth: production authorization, environment safety, real service
integration, real browser workflows, and security/CI enforcement are not yet
covered.

The next implementation phase should begin with failing P0 authentication and
production-startup tests. No tests should be weakened, and no feature work
should be added unless a production-readiness test requires it.
