# Production Readiness

Date: 2026-06-14

DocuQuery AI is a production-style portfolio application. It is not currently
ready for unrestricted public production deployment.

## Terms, Privacy, And Consent

- Public Terms of Service, Privacy Policy, and Cookie/Storage Policy pages are
  available in the frontend.
- Authenticated users and admins must accept the current Terms and Privacy
  versions before using protected application features.
- Acceptance stores the terms version, privacy version, and acceptance
  timestamp in browser `localStorage`.
- Changing either legal version causes the acceptance gate to appear again.
- A storage-consent manager supports Accept all, Reject optional, and Manage
  preferences.
- Necessary storage cannot be disabled.
- Optional analytics and marketing storage are disabled by default.
- No analytics or marketing cookies/scripts are currently installed.
- Users can withdraw or change optional choices through **Manage Cookie
  Preferences** in the application footer.

These pages and flows provide technical structure only. They require review and
replacement with organization-specific, lawyer-approved documents before a
real public deployment.

## Storage Used

Necessary browser storage:

- `docuquery_token`: signed API session token.
- `docuquery_legal_acceptance`: accepted Terms/Privacy versions and timestamp.
- `docuquery_storage_consent`: consent version, timestamp, and optional choices.

Optional browser storage:

- Analytics preference: supported but disabled by default; no analytics
  integration is installed.
- Marketing preference: supported but disabled by default; no marketing
  integration is installed.

See `docs/COOKIE_STORAGE_INVENTORY.md` for the complete technical inventory.

## AI Provider Readiness

- Chat generation and embedding generation are configured independently through
  provider-neutral environment variables.
- Supported OpenAI-compatible presets include `openai`, `openrouter`, `groq`,
  `mistral`, `together`, `deepseek`, `xai`, and `ollama`.
- Custom OpenAI-compatible endpoints are supported through `LLM_BASE_URL` and
  `EMBEDDING_BASE_URL`.
- The legacy `OPENAI_API_KEY` remains accepted as a shortcut for OpenAI-backed
  chat and embeddings.
- Provider keys are read server-side from environment variables; users do not
  enter provider keys in the browser.

This does not mean every model from every vendor is production-certified. Each
provider/model still needs a paid smoke test for embeddings, chat generation,
rate limits, context length, privacy terms, latency, and output quality.

## Demo-Grade Limitations

- Legal acceptance and consent choices are browser-level records, not linked to
  a durable user account.
- Browser timestamps and localStorage can be edited or cleared by the user.
- Authentication tokens are stored in localStorage.
- Authentication uses a shared admin password and anonymous user sessions
  rather than real user accounts.
- Logout removes the browser token but does not revoke previously issued
  stateless tokens.
- Rate limits and optimization jobs are stored in backend memory.
- Database schema updates are not managed with a versioned migration tool.
- PostgreSQL and Qdrant are exposed to host ports in the development Compose
  configuration.

## Required Before Real Public Production

- Store legal acceptance server-side per authenticated user, including document
  versions, timestamp, account ID, and an appropriate audit trail.
- Store consent choices server-side when they must follow a user across devices.
- Replace demo authentication with real accounts or an identity provider.
- Decide whether sessions should use secure, HttpOnly, SameSite cookies and
  implement CSRF protection if applicable.
- Obtain legal review for Terms, Privacy, retention, subprocessors, AI-provider
  disclosure, deletion requests, and regional consent requirements.
- Decide which AI providers are officially supported, document their data-use
  terms, and add provider-specific integration smoke tests.
- Define document/chat/evaluation retention and deletion policies.
- Add a process for publishing legal-version changes and requiring
  re-acceptance.
- Keep optional analytics/marketing scripts blocked until the corresponding
  stored consent is active.
- Expand CI with server-side authorization/integration/E2E/security test layers
  described in `docs/TEST_COVERAGE_REPORT.md`.
- Deploy PostgreSQL and Qdrant on private networks with credentials, backups,
  monitoring, and versioned migrations.

## Relevant Test Commands

```bash
docker compose run --rm frontend npm test -- --run
docker compose run --rm frontend npm run test:coverage
docker compose run --rm frontend npm run build
docker compose exec -T backend python -m unittest discover -s tests -v
```

This document is a technical readiness assessment, not legal advice.
