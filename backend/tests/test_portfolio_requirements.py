import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.auth import create_access_token, decode_access_token
from app.api.rate_limit import InMemoryRateLimiter
from app.db.models import Base, ChatLog, Document, EvaluationResult, Feedback
from app.rag.retriever import Retriever
from app.rag.vector_store import QdrantVectorStore
from app.services.chat_service import ChatService
from app.services.feedback_service import FeedbackService
from app.services.quality_service import QualityService
from app.utils.files import save_upload_file


class FakeRAG:
    def run(self, **kwargs):
        return {
            "answer": "The refund window is 30 days.",
            "sources": [{"filename": "policy.pdf", "page": 1}],
            "latency_seconds": 0.1,
            "settings_used": kwargs,
        }


class FailingRAG:
    def run(self, **kwargs):
        raise RuntimeError("provider unavailable")


class PortfolioRequirementTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()

    def tearDown(self):
        self.session.close()

    def test_quality_metrics_are_deterministic_and_explained(self):
        quality = QualityService()
        correctness = quality.answer_correctness(
            "Employees receive 20 days of annual leave.",
            "Employees receive 20 days of annual leave.",
        )
        faithfulness = quality.faithfulness(
            "Employees receive 20 days of annual leave.",
            ["The handbook says employees receive 20 days of annual leave."],
        )
        relevance = quality.context_relevance(
            "How much annual leave do employees receive?",
            ["The handbook says employees receive 20 days of annual leave."],
        )
        self.assertEqual(correctness["score"], 1.0)
        self.assertTrue(correctness["explanation"])
        self.assertGreater(faithfulness, 0.8)
        self.assertGreater(relevance, 0.3)

    def test_duplicate_original_filenames_get_unique_stored_filenames(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            def upload_path(filename):
                return str(Path(temp_dir) / filename)

            with patch("app.utils.files.get_upload_path", side_effect=upload_path):
                first_path, first_stored = save_upload_file(b"%PDF-1.4 first", "policy.pdf")
                second_path, second_stored = save_upload_file(b"%PDF-1.4 second", "policy.pdf")

            self.assertNotEqual(first_stored, second_stored)
            self.assertNotEqual(first_path, second_path)
            self.assertTrue(first_stored.endswith(".pdf"))
            self.assertEqual(Path(first_path).read_bytes(), b"%PDF-1.4 first")
            self.assertEqual(Path(second_path).read_bytes(), b"%PDF-1.4 second")

    def test_pdf_upload_rejects_non_pdf_content(self):
        with self.assertRaisesRegex(ValueError, "valid PDF"):
            save_upload_file(b"plain text", "fake.pdf")

    def test_auth_token_contains_session_and_expiration_is_enforced(self):
        token = create_access_token("user", session_id="session-a")
        context = decode_access_token(token)
        self.assertEqual(context.role, "user")
        self.assertEqual(context.session_id, "session-a")

        expired = create_access_token("user", session_id="session-a", expires_in_seconds=-1)
        with self.assertRaises(HTTPException):
            decode_access_token(expired)

    def test_chat_history_is_isolated_by_session_and_errors_are_not_answers(self):
        service = ChatService(self.session)
        service.rag = FakeRAG()
        first = service.process_chat("Refund?", session_id="session-a")
        service.process_chat("Refund?", session_id="session-b")

        history = service.get_chat_history(session_id="session-a")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["id"], first["chat_id"])
        self.assertEqual(self.session.query(ChatLog).count(), 2)

        service.rag = FailingRAG()
        with self.assertRaisesRegex(RuntimeError, "provider unavailable"):
            service.process_chat("Will this fail?", session_id="session-a")

    def test_document_original_filename_is_used_for_display(self):
        document = Document(
            filename="f8e3c7.pdf",
            original_filename="policy.pdf",
            file_path="f8e3c7.pdf",
        )
        self.session.add(document)
        self.session.commit()
        self.assertEqual(document.original_filename, "policy.pdf")

    def test_feedback_and_failed_question_analytics(self):
        chat = ChatLog(
            session_id="session-a",
            question="What is the refund window?",
            answer="It is 90 days.",
            sources_json="[]",
            no_chunks_retrieved=True,
        )
        evaluation = EvaluationResult(
            run_id=None,
            question="What is the refund window?",
            question_type="answerable",
            answer="It is 90 days.",
            retrieved_sources_json="[]",
            source_hit=False,
            faithfulness=0.2,
            no_chunks_retrieved=True,
        )
        self.session.add_all([chat, evaluation])
        self.session.commit()

        service = FeedbackService(self.session)
        feedback = service.create_feedback(chat.id, "session-a", "down", "Incorrect")
        analytics = service.failed_question_analytics()
        self.assertEqual(feedback["rating"], "down")
        self.assertEqual(len(analytics["bad_feedback"]), 1)
        self.assertEqual(len(analytics["low_faithfulness"]), 1)
        self.assertEqual(len(analytics["no_chunks"]), 2)
        self.assertEqual(len(analytics["answerable_source_miss"]), 1)

        retained_feedback = Feedback(
            session_id="session-a",
            chat_log_id=chat.id,
            rating="up",
            question=chat.question,
            answer=chat.answer,
            sources_json="[]",
        )
        self.session.add(retained_feedback)
        self.session.commit()

        cleared = service.clear_failed_question_analytics()
        self.assertEqual(cleared["failed_evaluation_results_deleted"], 1)
        self.assertEqual(cleared["no_chunk_chat_logs_deleted"], 1)
        self.assertEqual(cleared["bad_feedback_deleted"], 1)
        self.assertEqual(cleared["total_deleted"], 3)
        self.assertEqual(self.session.query(EvaluationResult).count(), 0)
        self.assertEqual(self.session.query(ChatLog).count(), 0)
        self.assertEqual(self.session.query(Feedback).filter(Feedback.rating == "down").count(), 0)
        self.assertEqual(self.session.query(Feedback).filter(Feedback.rating == "up").one().chat_log_id, None)
        empty = service.failed_question_analytics()
        self.assertTrue(all(len(items) == 0 for items in empty.values()))

    def test_rate_limiter_rejects_requests_over_limit(self):
        limiter = InMemoryRateLimiter()
        limiter.check("session-a", limit=2, window_seconds=60)
        limiter.check("session-a", limit=2, window_seconds=60)
        with self.assertRaises(HTTPException) as raised:
            limiter.check("session-a", limit=2, window_seconds=60)
        self.assertEqual(raised.exception.status_code, 429)


class HybridRetrieverTests(unittest.TestCase):
    def test_hybrid_combines_vector_and_keyword_results_and_reranks(self):
        retriever = Retriever.__new__(Retriever)
        retriever.embeddings = type("Embeddings", (), {"embed_text": lambda self, query: [1.0]})()
        retriever.vector_store = type(
            "VectorStore",
            (),
            {
                "search": lambda self, vector, top_k, with_vectors=False: [
                    {"id": 1, "text": "general policy", "score": 0.9},
                    {"id": 2, "text": "refund is available in 30 days", "score": 0.8},
                ],
                "keyword_search": lambda self, query, top_k: [
                    {"id": 2, "text": "refund is available in 30 days", "score": 1.0},
                    {"id": 3, "text": "refund exceptions", "score": 0.7},
                ],
            },
        )()

        results = retriever.retrieve("refund 30 days", top_k=2, method="hybrid", reranker="enabled")
        self.assertEqual(results[0]["id"], 2)
        self.assertEqual(len(results), 2)
        self.assertEqual([result["rank"] for result in results], [1, 2])


class QdrantIntegrationSmokeTests(unittest.TestCase):
    def test_temporary_collection_upsert_and_search(self):
        store = QdrantVectorStore()
        store.collection_name = f"docuquery_test_{uuid.uuid4().hex}"
        store.vector_size = 2
        reachable = store.check_connection()
        try:
            if not reachable:
                self.skipTest("Qdrant is not reachable")
            store.create_collection()
            ids = store.upsert_vectors(
                [[1.0, 0.0]],
                [{
                    "document_id": 1,
                    "filename": "test.pdf",
                    "page": 1,
                    "chunk_id": 1,
                    "text": "refund policy",
                    "preview": "refund policy",
                }],
            )
            self.assertEqual(len(ids), 1)
            results = store.search([1.0, 0.0], 1)
            self.assertEqual(results[0]["filename"], "test.pdf")
        finally:
            if reachable and store.collection_exists():
                store.client.delete_collection(store.collection_name)


if __name__ == "__main__":
    unittest.main()
