# GitLab Demo Runbook

Use this checklist when running the real-key GitLab public-document demo locally.

## Before Starting

- Do not commit `.env`, screenshots containing keys, or provider billing pages.
- Use a provider key with spending limits or billing alerts.
- Keep `PROVIDER_SETTINGS_ENCRYPTION_KEY` different from `AUTH_SECRET_KEY`.
- This demo uses public GitLab documentation only and is not affiliated with GitLab.

## Environment Checklist

Set these in `.env` before starting Docker:

```env
APP_ENV=development
AUTH_SECRET_KEY=replace_with_a_long_random_secret
ADMIN_PASSWORD=replace_with_a_secure_admin_password
PROVIDER_SETTINGS_ENCRYPTION_KEY=replace_with_a_different_long_random_secret
CORS_ORIGINS=http://localhost:5174
TRUST_PROXY_HEADERS=false
```

For a real production deployment, use `APP_ENV=production`, HTTPS, strict deployed CORS origins, and `REDIS_URL` or gateway-level rate limits.

## Start The App

```powershell
docker compose up --build -d
```

Open:

- Frontend: `http://localhost:5174`
- API docs: `http://localhost:8081/docs`
- Qdrant dashboard: `http://localhost:6333/dashboard`

## Configure AI Settings

1. Sign in as admin with `ADMIN_PASSWORD`.
2. Open **AI Settings**.
3. Enter the LLM provider, LLM model, and LLM API key.
4. Enter the embedding provider, embedding model, and embedding API key.
5. Save settings.
6. Confirm the UI shows `Configured` and only masked key placeholders.

Do not use a real key in screenshots unless it is fully masked.
If you choose Anthropic Claude for the LLM, choose a separate embedding provider such as OpenAI, Gemini, or Ollama. If you change the embedding provider/model or saved chunk size/overlap/strategy, the app marks existing vectors as stale; re-index documents before chat. Evaluation re-indexes before running the selected configuration.

## Load GitLab Documents

Upload all PDFs from:

```text
demo_public/gitlab/documents/
```

Expected files:

- `gitlab_communication_handbook.pdf`
- `gitlab_support_team_handbook.pdf`
- `gitlab_people_group.pdf`
- `gitlab_customer_service_guidance.pdf`
- `gitlab_support_on_call_guide.pdf`
- `gitlab_security_at_gitlab.pdf`
- `gitlab_service_desk_docs.pdf`

After upload, re-index the documents.

## Smoke Chat Questions

Ask a few questions before running the full evaluation:

- What communication approach does GitLab use as a starting point for remote work?
- What should support do when a customer request needs emergency attention?
- How does GitLab Service Desk create issues from customer emails?
- What is GitLab's private internal API key?

The last question should be refused because it is not available in the provided documents.

## Run Evaluation

Upload:

```text
demo_public/gitlab/evaluation/gitlab_evaluation.csv
```

Run with a simple baseline first:

- Chunk size: `800`
- Chunk overlap: `100`
- Top K: `5`
- Retrieval method: `similarity`
- Reranker: `none`

Then optionally run one optimization job if time and API budget allow.

## Save Portfolio Evidence

Save outputs under:

```text
demo_public/gitlab/results/
```

Recommended artifacts:

- Evaluation summary screenshot.
- Per-question evaluation export, if available.
- Screenshot of AI Settings showing masked keys.
- Screenshot of document list after upload/indexing.
- 2-3 chat screenshots with citations.
- Notes about settings used and any weak answers.

Use `RESULTS_TEMPLATE.md` as the summary format.

## If Something Fails

- If login fails, check `ADMIN_PASSWORD`.
- If AI Settings fails to save, check provider, model, base URL, and key format.
- If indexing fails, confirm the embedding key is set and has quota.
- If chat fails with provider errors, confirm the LLM key/model/base URL.
- If evaluation is expensive, stop after the baseline run and save honest partial results.
