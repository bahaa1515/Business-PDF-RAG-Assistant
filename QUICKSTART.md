# 🎯 Quick Start Guide - DocuQuery AI

## ⚡ 60-Second Setup

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Edit .env and add your AI provider keys
# LLM_API_KEY=...
# EMBEDDING_API_KEY=...

# 3. Start everything
docker-compose up --build

# 4. Open browser
# Frontend: http://localhost:5174
# API Docs: http://localhost:8081/docs
```

**That's it!** All services start automatically:
- PostgreSQL (host port 5433)
- Qdrant (port 6333)
- FastAPI Backend (host port 8081)
- React Frontend (host port 5174)

---

## 📝 First Steps

### 1. Upload a Test Document

1. Go to http://localhost:5174
2. Click "📄 Documents" in sidebar
3. Upload the sample PDFs from `demo/documents/` or any business PDF
4. Status should show "uploaded"

### 2. Re-Index Documents

1. On Documents page, click "Re-index Documents"
2. Wait for status to change to "indexed"
3. Verify chunk_count is populated (e.g., "42 chunks")

### 3. Ask a Question

1. Click "💬 Chat" in sidebar
2. Ask a question about your PDF (e.g., "What is in this document?")
3. See answer with source citations
4. Toggle "Show retrieval debug" to see retrieved chunks

### 4. Run Evaluation

1. Use `demo/evaluation/sample_evaluation.csv` or `eval/evaluation_questions.csv`
2. Click "📊 Evaluation"
3. Click "Run Evaluation"
4. See metrics: source hit rate, refusal accuracy, latency
5. (Advanced) Click "Run Optimization" for grid search

---

## 🛠️ File Structure Quick Reference

```
Backend Python Files:
├── app/config.py              ← All settings
├── app/main.py                ← FastAPI entry point
├── app/api/*.py               ← 4 endpoint files
├── app/rag/*.py               ← 8 pipeline modules
├── app/services/*.py          ← 3 service files
├── app/db/*.py                ← Database models & connection
└── requirements.txt           ← Python packages

Frontend JavaScript:
├── src/App.jsx                ← Main app
├── src/pages/*.jsx            ← 3 page components
├── src/components/*.jsx       ← 7 UI components
├── src/api/client.js          ← Backend HTTP client
└── package.json               ← Dependencies

Infrastructure:
├── docker-compose.yml         ← All services
├── .env.example               ← Settings template
└── README.md                  ← Full documentation
```

---

## 🧪 Testing Checklist

- [ ] Backend health: `curl http://localhost:8081/health`
- [ ] Upload PDF via UI
- [ ] Re-index documents
- [ ] Ask a question in chat
- [ ] See source citations
- [ ] View retrieval debug
- [ ] Run evaluation
- [ ] Check API docs: http://localhost:8081/docs

---

## 🐛 Troubleshooting

### "Connection refused: localhost:5433"
PostgreSQL not running. Check:
```bash
docker-compose ps
docker-compose logs postgres
```

### "Connection refused: localhost:6333"
Qdrant not running:
```bash
docker-compose logs qdrant
```

### "LLM_API_KEY is required" or "EMBEDDING_API_KEY is required"
Make sure `.env` exists with your provider keys:
```bash
cat .env | grep API_KEY
```

### Backend won't start after first run
Check database initialization:
```bash
docker-compose exec backend python -m app.db.init_db
```

### Clear everything and restart
```bash
docker-compose down -v
rm -rf postgres_data qdrant_storage
docker-compose up --build
```

---

## 📊 Evaluation CSV Format

Use `demo/evaluation/sample_evaluation.csv` for the demo walkthrough, or create
an evaluation CSV with exactly these columns:
```csv
question,reference_answer,expected_source,expected_page,question_type
"What is the refund window?","Customers may request a refund within 30 days.",refund_policy.pdf,1,answerable
"What is the CEO's private phone number?",,,,unanswerable
```

Answerable rows require `reference_answer`, `expected_source`, and
`expected_page`. Unanswerable rows must leave those three fields empty.

---

## 🔐 Environment Variables

**Required:**
- `LLM_PROVIDER` / `LLM_API_KEY` / `LLM_MODEL` - Chat provider configuration
- `EMBEDDING_PROVIDER` / `EMBEDDING_API_KEY` / `EMBEDDING_MODEL` - Embedding provider configuration
- `OPENAI_API_KEY` - Backward-compatible shortcut for OpenAI-backed chat and embeddings

**Optional (Docker Compose defaults):**
- `DATABASE_URL` - PostgreSQL connection
- `QDRANT_URL` - Qdrant URL
- `BACKEND_PORT` - FastAPI port (default 8000)
- `FRONTEND_PORT` - React port (default 5173)

---

## 📈 Performance Tips

1. **Chunk size**: Larger chunks (1200) for broad topics, smaller (400) for detailed content
2. **Top K**: More (5-10) for diverse answers, fewer (3) for focused results
3. **Overlap**: More overlap helps preserve context, increases latency
4. **Batch size**: Test with 5-10 docs first, then scale

---

## 🎨 Frontend Navigation

| Page | Purpose | Key Features |
|------|---------|--------------|
| **Chat** | Ask questions | Source citations, debug view, history |
| **Documents** | Manage PDFs | Upload, re-index, delete, settings |
| **Evaluation** | Test RAG | Run eval, optimize, metrics, CSV export |

---

## 🔌 Main API Endpoints

```bash
# Documents
POST   /documents/upload              # Upload PDFs
GET    /documents/                    # List all
DELETE /documents/{id}                # Delete one
POST   /documents/reindex             # Re-index all
POST   /documents/reset-index         # Clear vector store

# Chat
POST   /chat/                         # Ask question
GET    /chat/history                  # Get chat logs
DELETE /chat/history                  # Clear chat

# Evaluation
POST   /evaluation/run                # Run evaluation
POST   /optimization/run              # Run optimization

# Authentication
POST   /auth/login                    # Create user/admin session
GET    /auth/me                       # Verify current session

# System
GET    /health                        # Health check
```

Full interactive docs: http://localhost:8081/docs

Admin actions require a bearer token returned by `/auth/login`. Set a secure
`ADMIN_PASSWORD` and `AUTH_SECRET_KEY` in `.env` before sharing the app.

---

## 📚 Example Workflows

### Workflow 1: Quick Demo
1. Upload sample PDF (2-5 pages)
2. Re-index (takes ~10 seconds)
3. Ask 3-5 questions
4. Show source citations
5. Toggle debug view

### Workflow 2: Evaluate RAG Quality
1. Start from `demo/evaluation/sample_evaluation.csv` and expand it to 10-20 questions
2. Re-index with default settings (800/100)
3. Run evaluation
4. Review metrics
5. Manually test borderline cases

### Workflow 3: Optimize Performance
1. Prepare evaluation CSV with representative questions
2. Run optimization experiments
3. Review results ranked by source_hit_rate
4. Apply best configuration
5. Re-index and verify

---

## 🚀 Production Deployment Notes

**For production, consider:**
- Move secrets to AWS Secrets Manager / HashiCorp Vault
- Add authentication (OAuth 2.0 / OIDC)
- Deploy backend to AWS ECS / Google Cloud Run
- Deploy frontend to Vercel / CloudFlare Pages
- Use managed PostgreSQL (AWS RDS, GCP Cloud SQL)
- Use managed Qdrant (Qdrant Cloud)
- Add monitoring (DataDog, New Relic)
- Enable HTTPS/TLS
- Expand CI/CD with linting, security scans, and E2E gates
- Configure auto-scaling

---

## 📞 Support

**Read the comprehensive README:**
```bash
cat README.md
```

**Check logs:**
```bash
docker-compose logs -f [service]
# service: backend, frontend, postgres, qdrant
```

**API documentation:**
http://localhost:8081/docs (Swagger UI)
http://localhost:8081/redoc (ReDoc)

---

**Ready to go! Start with `docker-compose up --build` 🚀**
