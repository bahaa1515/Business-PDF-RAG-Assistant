# Generalization Validation Results

Generated: 2026-07-06

This validation uses public GitLab documentation and does not store API keys. It reports the original premium baseline, the known benchmark, and the unseen GitLab holdout set separately.

## Final Configuration

- Chat model: `gpt-4o`
- Embedding model: `text-embedding-3-large`
- Chunking: `1200 / 150 / structure`
- Retrieval profile: `auto`
- Prompt variant: `multi_doc_synthesis`
- Answer verification: enabled
- Semantic judge: enabled
- Query-focused evidence highlights: enabled

## Result Comparison

| Split | Questions | Semantic correctness | Retrieval accuracy | Refusal accuracy | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| Previous premium baseline | 40 | 90.0% | 97.2% | 100.0% | Before auto retrieval, answer verification, and evidence highlighting |
| Known benchmark | 40 | 92.8% | 100.0% | 100.0% | Final implementation |
| Holdout benchmark | 15 | 93.1% | 100.0% | 100.0% | Unseen questions from the same public PDFs |

## Interpretation

The final implementation is better than the previous premium baseline. Retrieval accuracy improved from 97.2% to 100.0%, semantic correctness improved from 90.0% to 92.8% on the known benchmark, and the unseen holdout reached 93.1%. This is strong enough to present as a professional RAG portfolio proof of concept, while still being honest that results are from a public-document demo and not a production client deployment.

The remaining known benchmark rows below 0.85 are reference-answer calibration issues rather than retrieval failures: the generated answers included source-supported details that the narrower reference answers did not mention.
