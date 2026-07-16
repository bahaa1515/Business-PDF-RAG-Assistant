# Upwork Portfolio Asset Pack

Generated: 2026-07-06

These assets present DocuQuery AI as a public-document RAG portfolio case study. The GitLab documentation demo uses public documents only and is not affiliated with or endorsed by GitLab.

## Final Screenshots

Use the images in `screenshots_final/` for the portfolio item. These replace the earlier rough screenshots.

1. `screenshots_final/01-ai-settings-masked-openai.png`  
   Admin-only provider settings with masked OpenAI chat and embedding keys.

2. `screenshots_final/02-documents-indexed-gitlab.png`  
   GitLab public-document set indexed with structure-aware chunking.

3. `screenshots_final/03-evaluation-final-metrics.png`  
   Final known benchmark result: 92.8% semantic correctness, 100.0% retrieval accuracy, 100.0% refusal accuracy.

4. `screenshots_final/04-optimization-config.png`  
   Bounded optimization controls for chunking, retrieval, reranking, prompt variants, and semantic judging.

5. `screenshots_final/05-chat-cited-answer.png`  
   Chat UI proof with citation-grounded answer and retrieved source cards.

## Final Validation Results

| Split | Questions | Semantic correctness | Retrieval accuracy | Refusal accuracy |
| --- | ---: | ---: | ---: | ---: |
| Previous premium baseline | 40 | 90.0% | 97.2% | 100.0% |
| Known benchmark | 40 | 92.8% | 100.0% | 100.0% |
| Holdout benchmark | 15 | 93.1% | 100.0% | 100.0% |

## Validation Checks

- Backend unittest suite: 94 tests passed.
- Docker backend rebuilt and restarted with the final implementation.
- Health check: database and vector store connected.
- Final documents: 7 GitLab PDFs indexed with `1200 / 150 / structure`.
- Qdrant vector dimension: 3072 for `text-embedding-3-large`.

Use this wording honestly: "Validated locally on a public GitLab documentation case study. Results are portfolio/demo evidence, not production client results."
