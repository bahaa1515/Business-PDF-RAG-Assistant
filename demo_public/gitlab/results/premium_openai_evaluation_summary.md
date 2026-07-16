# Premium OpenAI Evaluation Summary

- Model: gpt-4o
- Embedding model: text-embedding-3-large
- Prompt variant: multi_doc_synthesis
- Chunk size: 1200
- Chunk overlap: 150
- Chunking strategy: structure
- Top K: 8
- Retrieval method: mmr
- Reranker: none
- Questions: 40
- Answerable: 36
- Unanswerable: 4
- Retrieval accuracy: 0.972
- Semantic answer correctness: 0.900
- Refusal accuracy: 1.000
- Average latency seconds: 2.970

The final score comes from a bounded smart prompt/retrieval optimization: 8 probe configurations on 12 representative questions, then a full 40-question validation of the best completed configuration. Legacy lexical overlap diagnostics are retained in the raw JSON for debugging but are not used as portfolio headline metrics.

This is a local portfolio validation run using public GitLab documentation. It is not affiliated with or endorsed by GitLab.
