"""
PostgreSQL database connection and session management.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

from app.config import DATABASE_URL
from app.db.models import Base


# Create engine with connection pooling disabled for better compatibility
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,
    echo=False,
    connect_args={"connect_timeout": 10}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize tables and apply small additive migrations."""
    Base.metadata.create_all(bind=engine)
    migrations = {
        "documents": [
            "ADD COLUMN IF NOT EXISTS original_filename VARCHAR(255)",
            "ADD COLUMN IF NOT EXISTS document_type VARCHAR(32) DEFAULT 'pdf'",
            "ADD COLUMN IF NOT EXISTS content_unit_count INTEGER DEFAULT 0",
            "ADD COLUMN IF NOT EXISTS chunking_strategy VARCHAR(32) DEFAULT 'auto'",
        ],
        "chat_logs": [
            "ADD COLUMN IF NOT EXISTS session_id VARCHAR(64)",
            "ADD COLUMN IF NOT EXISTS reranker VARCHAR(50) DEFAULT 'none'",
            "ADD COLUMN IF NOT EXISTS prompt_variant VARCHAR(64)",
            "ADD COLUMN IF NOT EXISTS retrieval_profile VARCHAR(64)",
            "ADD COLUMN IF NOT EXISTS resolved_retrieval_profile VARCHAR(64)",
            "ADD COLUMN IF NOT EXISTS answer_verification BOOLEAN DEFAULT FALSE",
            "ADD COLUMN IF NOT EXISTS no_chunks_retrieved BOOLEAN DEFAULT FALSE",
            "ADD COLUMN IF NOT EXISTS chunking_strategy VARCHAR(32)",
            "ADD COLUMN IF NOT EXISTS document_type VARCHAR(32)",
            "ADD COLUMN IF NOT EXISTS content_unit_count INTEGER",
        ],
        "evaluation_runs": [
            "ADD COLUMN IF NOT EXISTS answer_correctness DOUBLE PRECISION",
            "ADD COLUMN IF NOT EXISTS semantic_answer_correctness DOUBLE PRECISION",
            "ADD COLUMN IF NOT EXISTS faithfulness DOUBLE PRECISION",
            "ADD COLUMN IF NOT EXISTS context_relevance DOUBLE PRECISION",
            "ADD COLUMN IF NOT EXISTS answerable_questions INTEGER",
            "ADD COLUMN IF NOT EXISTS unanswerable_questions INTEGER",
            "ADD COLUMN IF NOT EXISTS prompt_variant VARCHAR(64)",
            "ADD COLUMN IF NOT EXISTS benchmark_split VARCHAR(32) DEFAULT 'known'",
            "ADD COLUMN IF NOT EXISTS retrieval_profile VARCHAR(64)",
            "ADD COLUMN IF NOT EXISTS answer_verification BOOLEAN DEFAULT FALSE",
            "ADD COLUMN IF NOT EXISTS llm_model VARCHAR(255)",
            "ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(255)",
        ],
        "evaluation_results": [
            "ADD COLUMN IF NOT EXISTS reference_answer TEXT",
            "ADD COLUMN IF NOT EXISTS expected_locator VARCHAR(255)",
            "ADD COLUMN IF NOT EXISTS answer_correctness DOUBLE PRECISION",
            "ADD COLUMN IF NOT EXISTS correctness_explanation TEXT",
            "ADD COLUMN IF NOT EXISTS semantic_answer_correctness DOUBLE PRECISION",
            "ADD COLUMN IF NOT EXISTS semantic_verdict VARCHAR(32)",
            "ADD COLUMN IF NOT EXISTS semantic_explanation TEXT",
            "ADD COLUMN IF NOT EXISTS faithfulness DOUBLE PRECISION",
            "ADD COLUMN IF NOT EXISTS context_relevance DOUBLE PRECISION",
            "ADD COLUMN IF NOT EXISTS no_chunks_retrieved BOOLEAN DEFAULT FALSE",
            "ADD COLUMN IF NOT EXISTS top_k INTEGER",
            "ADD COLUMN IF NOT EXISTS retrieval_method VARCHAR(50)",
            "ADD COLUMN IF NOT EXISTS reranker VARCHAR(50)",
            "ADD COLUMN IF NOT EXISTS chunking_strategy VARCHAR(32)",
            "ADD COLUMN IF NOT EXISTS prompt_variant VARCHAR(64)",
            "ADD COLUMN IF NOT EXISTS retrieval_profile VARCHAR(64)",
            "ADD COLUMN IF NOT EXISTS resolved_retrieval_profile VARCHAR(64)",
            "ADD COLUMN IF NOT EXISTS answer_verification BOOLEAN DEFAULT FALSE",
            "ADD COLUMN IF NOT EXISTS document_type VARCHAR(32)",
            "ADD COLUMN IF NOT EXISTS content_unit_count INTEGER",
        ],
        "optimization_results": [
            "ADD COLUMN IF NOT EXISTS reranker VARCHAR(50) DEFAULT 'none'",
            "ADD COLUMN IF NOT EXISTS prompt_variant VARCHAR(64)",
            "ADD COLUMN IF NOT EXISTS chunking_strategy VARCHAR(32) DEFAULT 'auto'",
            "ADD COLUMN IF NOT EXISTS document_type VARCHAR(32)",
            "ADD COLUMN IF NOT EXISTS content_unit_count INTEGER",
            "ADD COLUMN IF NOT EXISTS answer_correctness DOUBLE PRECISION",
            "ADD COLUMN IF NOT EXISTS semantic_answer_correctness DOUBLE PRECISION",
            "ADD COLUMN IF NOT EXISTS faithfulness DOUBLE PRECISION",
            "ADD COLUMN IF NOT EXISTS context_relevance DOUBLE PRECISION",
            "ADD COLUMN IF NOT EXISTS total_questions INTEGER",
            "ADD COLUMN IF NOT EXISTS answerable_questions INTEGER",
            "ADD COLUMN IF NOT EXISTS unanswerable_questions INTEGER",
        ],
    }
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            for table, statements in migrations.items():
                for statement in statements:
                    connection.execute(text(f"ALTER TABLE {table} {statement}"))
            connection.execute(
                text(
                    "UPDATE documents SET original_filename = filename "
                    "WHERE original_filename IS NULL"
                )
            )


def get_db() -> Session:
    """Get database session (for FastAPI dependency injection)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """Check if database is reachable."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False
