# GitLab Public Documentation Case Study

This case study demonstrates DocuQuery AI on public business-document content that resembles a real internal knowledge base. It uses publicly available GitLab documentation only. GitLab is not a client, sponsor, or endorser of this project.

## Why This Document Set

GitLab publishes extensive handbook, support, people-operations, security, and product documentation. That makes it a strong public proxy for the kinds of PDFs a company might upload to DocuQuery AI for customer support and internal knowledge management.

The selected sources cover:

- General company operations and communication norms.
- Support team operations and customer-facing support processes.
- People/HR-style policies and People Operations workflows.
- Customer service behavior and ticket handling guidance.
- Support on-call and emergency-support operations.
- Security operations and incident-reporting guidance.
- Product documentation for GitLab Service Desk.

The web pages were converted into clean PDFs so the demo uses the same PDF upload workflow as the rest of DocuQuery AI. Navigation, sidebar, cookie banner, and unrelated website chrome were omitted where possible.

## Business Scenario Simulated

The scenario is a support and internal-knowledge assistant for a company with distributed teams and a large written handbook. Users may ask practical questions such as:

- How should a support engineer manage customer expectations?
- Where should internal support decisions be documented?
- What should an on-call engineer do during an emergency handoff?
- How does a support-related product feature behave?
- What information is not present in the approved document set?

This simulates a real RAG workflow without using private company data, scraped personal data, leaked documents, customer records, or API secrets.

## Evaluation Coverage

The evaluation CSV contains 40 questions with the required columns:

`question,reference_answer,expected_source,expected_page,question_type`

A separate holdout CSV contains 15 fresh questions from the same PDFs:

```text
demo_public/gitlab/evaluation/gitlab_holdout_evaluation.csv
```

Use the 40-question file as the known benchmark and the holdout file as an unseen generalization check. Do not edit benchmark references after viewing model failures just to raise the score.

The questions cover:

- Factual lookup.
- Policy and procedure retrieval.
- Customer support behavior.
- Product and technical documentation.
- Multi-document reasoning.
- Unanswerable questions.
- Ambiguous or edge-case questions.

For unanswerable questions, the reference answer says that the answer is not available in the provided documents, and `expected_source` / `expected_page` are set to `none`.

## How To Run In DocuQuery AI

1. Start the app locally:

```bash
docker compose up --build -d
```

2. Open the frontend at `http://localhost:5174`.
3. Sign in as an admin using the local `ADMIN_PASSWORD` configured in `.env`.
4. Upload every PDF from:

```text
demo_public/gitlab/documents/
```

5. Re-index the uploaded documents.
6. Open the Evaluation workflow.
7. Upload:

```text
demo_public/gitlab/evaluation/gitlab_evaluation.csv
```

8. For generalization validation, also run the holdout file:

```text
demo_public/gitlab/evaluation/gitlab_holdout_evaluation.csv
```

9. Run paid validation only after configuring real provider credentials locally through environment variables or the admin AI Settings page.
10. Keep paid validation bounded. The guarded script defaults to dry-run mode:

```bash
python scripts/run_generalization_validation.py
```

To intentionally run the paid validation pass after checking the OpenAI dashboard budget:

```bash
python scripts/run_generalization_validation.py --allow-paid --budget-ceiling-usd 3
```

11. Save exported evaluation outputs, screenshots, or metric summaries under:

```text
demo_public/gitlab/results/
```

## Results To Save Later

No real API benchmark results are included in this repository.

After local validation with real API credentials, save evidence such as:

- Evaluation summary metrics.
- Per-question evaluation export.
- Retrieval/source-hit examples.
- Screenshots of grounded answers with citations.
- Notes about retrieval settings used for the run.
- Any failed or weak questions that should guide future tuning.

Do not add fabricated accuracy, latency, cost, or source-hit claims. If a result was produced with deterministic tests, local mocks, or a sample/demo mode, label it as such.

## Portfolio Presentation Guidance

Present this as a public-document RAG case study, not a client project. Suitable language:

> Built a public-document RAG case study using GitLab's publicly available documentation to simulate an internal support knowledge base. The demo includes attributed source PDFs, a 40-question evaluation set, and placeholders for real API validation results.

Avoid saying or implying:

- GitLab is a customer or client.
- The project used private GitLab data.
- The repository contains production benchmark results.
- The demo was validated with paid LLM calls unless that validation has actually been run locally and documented.

## Files

- Sources and attribution: `source_links.md`
- PDFs: `documents/`
- Evaluation CSV: `evaluation/gitlab_evaluation.csv`
- Demo runbook: `DEMO_RUNBOOK.md`
- Future validation outputs: `results/`
  - Results template: `results/RESULTS_TEMPLATE.md`
