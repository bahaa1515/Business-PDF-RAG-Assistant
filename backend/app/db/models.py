"""
SQLAlchemy ORM models for PostgreSQL database.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Document(Base):
    """Document metadata stored in PostgreSQL."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), index=True)
    original_filename = Column(String(255), index=True)
    file_path = Column(String(512))
    upload_time = Column(DateTime, default=datetime.utcnow, index=True)
    document_type = Column(String(32), default="pdf", index=True)
    page_count = Column(Integer, default=0)
    content_unit_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    status = Column(String(50), default="uploaded")  # uploaded, indexed, needs_reindex, failed
    chunk_size = Column(Integer, default=800)
    chunk_overlap = Column(Integer, default=100)
    chunking_strategy = Column(String(32), default="auto")

    # Relationships
    chat_logs = relationship("ChatLog", back_populates="document")

    def __repr__(self):
        return f"<Document {self.id}: {self.filename}>"


class ChatLog(Base):
    """Chat messages and RAG responses stored in PostgreSQL."""
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    session_id = Column(String(64), index=True)
    question = Column(Text)
    answer = Column(Text)
    sources_json = Column(Text)  # JSON string of sources
    latency_seconds = Column(Float)
    top_k = Column(Integer)
    retrieval_method = Column(String(50))  # similarity, mmr, hybrid
    reranker = Column(String(50), default="none")
    prompt_variant = Column(String(64), nullable=True)
    retrieval_profile = Column(String(64), nullable=True)
    resolved_retrieval_profile = Column(String(64), nullable=True)
    answer_verification = Column(Boolean, default=False)
    no_chunks_retrieved = Column(Boolean, default=False)
    chunk_size = Column(Integer)
    chunk_overlap = Column(Integer)
    chunking_strategy = Column(String(32), nullable=True)
    document_type = Column(String(32), nullable=True)
    content_unit_count = Column(Integer, nullable=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)

    # Relationships
    document = relationship("Document", back_populates="chat_logs")

    def __repr__(self):
        return f"<ChatLog {self.id}: {self.timestamp}>"


class EvaluationRun(Base):
    """Evaluation run metadata."""
    __tablename__ = "evaluation_runs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    source_hit_rate = Column(Float)
    refusal_accuracy = Column(Float)
    answer_correctness = Column(Float)
    semantic_answer_correctness = Column(Float, nullable=True)
    faithfulness = Column(Float)
    context_relevance = Column(Float)
    average_latency = Column(Float)
    total_questions = Column(Integer)
    answerable_questions = Column(Integer)
    unanswerable_questions = Column(Integer)
    prompt_variant = Column(String(64), nullable=True)
    benchmark_split = Column(String(32), default="known")
    retrieval_profile = Column(String(64), nullable=True)
    answer_verification = Column(Boolean, default=False)
    llm_model = Column(String(255), nullable=True)
    embedding_model = Column(String(255), nullable=True)

    # Relationships
    results = relationship("EvaluationResult", back_populates="run")

    def __repr__(self):
        return f"<EvaluationRun {self.id}>"


class EvaluationResult(Base):
    """Individual evaluation question result."""
    __tablename__ = "evaluation_results"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("evaluation_runs.id"))
    question = Column(Text)
    question_type = Column(String(50))  # answerable, unanswerable
    reference_answer = Column(Text, nullable=True)
    expected_source = Column(String(255), nullable=True)
    expected_page = Column(Integer, nullable=True)
    expected_locator = Column(String(255), nullable=True)
    answer = Column(Text)
    retrieved_sources_json = Column(Text)
    source_hit = Column(Boolean, nullable=True)  # True if correct, False if wrong, None if unanswerable
    correctly_refused = Column(Boolean, nullable=True)
    answer_correctness = Column(Float, nullable=True)
    correctness_explanation = Column(Text, nullable=True)
    semantic_answer_correctness = Column(Float, nullable=True)
    semantic_verdict = Column(String(32), nullable=True)
    semantic_explanation = Column(Text, nullable=True)
    faithfulness = Column(Float, nullable=True)
    context_relevance = Column(Float, nullable=True)
    no_chunks_retrieved = Column(Boolean, default=False)
    top_k = Column(Integer, nullable=True)
    retrieval_method = Column(String(50), nullable=True)
    reranker = Column(String(50), nullable=True)
    chunking_strategy = Column(String(32), nullable=True)
    prompt_variant = Column(String(64), nullable=True)
    retrieval_profile = Column(String(64), nullable=True)
    resolved_retrieval_profile = Column(String(64), nullable=True)
    answer_verification = Column(Boolean, default=False)
    document_type = Column(String(32), nullable=True)
    content_unit_count = Column(Integer, nullable=True)
    latency_seconds = Column(Float)

    # Relationships
    run = relationship("EvaluationRun", back_populates="results")

    def __repr__(self):
        return f"<EvaluationResult {self.id}>"


class OptimizationRun(Base):
    """Optimization experiment run metadata."""
    __tablename__ = "optimization_runs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    notes = Column(String(255), nullable=True)

    # Relationships
    results = relationship("OptimizationResult", back_populates="run")

    def __repr__(self):
        return f"<OptimizationRun {self.id}>"


class OptimizationResult(Base):
    """Individual optimization experiment configuration result."""
    __tablename__ = "optimization_results"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("optimization_runs.id"))
    chunk_size = Column(Integer)
    chunk_overlap = Column(Integer)
    chunking_strategy = Column(String(32), default="auto")
    document_type = Column(String(32), nullable=True)
    content_unit_count = Column(Integer, nullable=True)
    top_k = Column(Integer)
    retrieval_method = Column(String(50))
    reranker = Column(String(50), default="none")
    prompt_variant = Column(String(64), nullable=True)
    source_hit_rate = Column(Float)
    refusal_accuracy = Column(Float)
    answer_correctness = Column(Float)
    semantic_answer_correctness = Column(Float, nullable=True)
    faithfulness = Column(Float)
    context_relevance = Column(Float)
    average_latency = Column(Float)
    total_questions = Column(Integer)
    answerable_questions = Column(Integer)
    unanswerable_questions = Column(Integer)

    # Relationships
    run = relationship("OptimizationRun", back_populates="results")

    def __repr__(self):
        return f"<OptimizationResult {self.id}>"


class Feedback(Base):
    """User feedback attached to a stored chat answer."""
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    session_id = Column(String(64), index=True)
    chat_log_id = Column(Integer, ForeignKey("chat_logs.id"), nullable=True, index=True)
    rating = Column(String(10))  # up, down
    comment = Column(Text, nullable=True)
    question = Column(Text)
    answer = Column(Text)
    sources_json = Column(Text)


class ProviderSetting(Base):
    """Encrypted admin-managed AI provider configuration."""
    __tablename__ = "provider_settings"

    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(32), unique=True, nullable=False, index=True)  # llm, embedding
    provider = Column(String(64), nullable=False)
    model = Column(String(255), nullable=False)
    base_url = Column(String(512), nullable=True)
    encrypted_api_key = Column(Text, nullable=True)
    api_key_fingerprint = Column(String(64), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)


class IndexConfiguration(Base):
    """Admin-selected document indexing configuration."""
    __tablename__ = "index_configurations"

    id = Column(Integer, primary_key=True)
    chunk_size = Column(Integer, nullable=False, default=800)
    chunk_overlap = Column(Integer, nullable=False, default=100)
    chunking_strategy = Column(String(32), nullable=False, default="auto")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
