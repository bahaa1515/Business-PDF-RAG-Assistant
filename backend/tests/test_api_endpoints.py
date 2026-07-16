import io
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.auth import create_access_token
from app.api.rate_limit import rate_limiter
from app.db.database import get_db
from app.main import app


class ApiEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db] = lambda: MagicMock()
        cls.client = TestClient(app)
        cls.user_headers = {
            "Authorization": f"Bearer {create_access_token('user', session_id='api-user')}"
        }
        cls.admin_headers = {
            "Authorization": f"Bearer {create_access_token('admin', session_id='api-admin')}"
        }

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()

    def setUp(self):
        rate_limiter._events.clear()
        self.client.cookies.clear()

    def test_auth_login_me_and_admin_rejection(self):
        login = self.client.post("/auth/login", json={"role": "user"})
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.json()["session_id"])

        me = self.client.get("/auth/me", headers=self.user_headers)
        self.assertEqual(me.json()["role"], "user")

        invalid = self.client.post(
            "/auth/login", json={"role": "admin", "password": "wrong"}
        )
        self.assertEqual(invalid.status_code, 401)

    @patch("app.api.health.QdrantVectorStore")
    @patch("app.api.health.check_db_connection")
    def test_health_reports_healthy_and_degraded(self, db_check, vector_store):
        db_check.return_value = True
        vector_store.return_value.check_connection.return_value = True
        self.assertEqual(self.client.get("/health").json()["status"], "healthy")

        vector_store.return_value.check_connection.return_value = False
        self.assertEqual(self.client.get("/health").json()["status"], "degraded")

    @patch("app.api.chat.ChatService")
    def test_chat_enforces_user_defaults_and_returns_structured_error(self, service_cls):
        service_cls.return_value.process_chat.return_value = {"answer": "ok"}
        response = self.client.post(
            "/chat/",
            headers=self.user_headers,
            json={
                "question": "Hello",
                "top_k": 20,
                "retrieval_method": "hybrid",
                "reranker": "enabled",
                "show_debug": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        service_cls.return_value.process_chat.assert_called_once_with(
            question="Hello",
            session_id="api-user",
            top_k=5,
            retrieval_method="similarity",
            reranker="none",
            prompt_variant=None,
            retrieval_profile="manual",
            answer_verification=False,
            show_debug=False,
        )

        service_cls.return_value.process_chat.side_effect = RuntimeError("provider down")
        failed = self.client.post(
            "/chat/", headers=self.user_headers, json={"question": "Fail"}
        )
        self.assertEqual(failed.status_code, 502)
        self.assertEqual(failed.json()["detail"]["code"], "rag_request_failed")

    @patch("app.api.chat.ChatService")
    def test_chat_admin_validation_history_and_clear(self, service_cls):
        invalid = self.client.post(
            "/chat/",
            headers=self.admin_headers,
            json={"question": "Hello", "top_k": 999},
        )
        self.assertEqual(invalid.status_code, 400)

        service_cls.return_value.get_chat_history.return_value = [{"id": 1}]
        history = self.client.get("/chat/history", headers=self.admin_headers)
        self.assertEqual(history.json()["total"], 1)
        service_cls.return_value.get_chat_history.assert_called_with(
            session_id="api-admin", limit=50, include_all=True
        )

        service_cls.return_value.clear_chat_history.return_value = True
        cleared = self.client.delete("/chat/history", headers=self.admin_headers)
        self.assertEqual(cleared.status_code, 200)

    @patch("app.api.documents.DocumentService")
    def test_document_endpoints(self, service_cls):
        forbidden = self.client.get("/documents/", headers=self.user_headers)
        self.assertEqual(forbidden.status_code, 403)

        anonymous_upload = self.client.post(
            "/documents/upload",
            files={"files": ("policy.pdf", b"%PDF-1.4", "application/pdf")},
        )
        self.assertEqual(anonymous_upload.status_code, 401)

        user_upload = self.client.post(
            "/documents/upload",
            headers=self.user_headers,
            files={"files": ("policy.pdf", b"%PDF-1.4", "application/pdf")},
        )
        self.assertEqual(user_upload.status_code, 403)

        service_cls.return_value.upload_file.return_value = {
            "uploaded": [],
            "rejected_files": [{"filename": "script.js", "reason": "Unsupported file type: .js"}],
            "total_uploaded": 0,
            "total_rejected": 1,
        }
        bad_upload = self.client.post(
            "/documents/upload",
            headers=self.admin_headers,
            files={"files": ("script.js", b"alert(1)", "text/javascript")},
        )
        self.assertEqual(bad_upload.status_code, 200)
        self.assertEqual(bad_upload.json()["total_rejected"], 1)

        service_cls.return_value.upload_file.return_value = {
            "uploaded": [{"id": 1, "filename": "policy.pdf"}],
            "rejected_files": [],
            "total_uploaded": 1,
            "total_rejected": 0,
        }
        uploaded = self.client.post(
            "/documents/upload",
            headers=self.admin_headers,
            files={"files": ("policy.pdf", b"%PDF-1.4", "application/pdf")},
        )
        self.assertEqual(uploaded.json()["total"], 1)

        service_cls.return_value.get_documents.return_value = [{"id": 1}]
        self.assertEqual(
            self.client.get("/documents/", headers=self.admin_headers).json()["total"], 1
        )

        service_cls.return_value.index_readiness.return_value = {"ready": True}
        index_status = self.client.get("/documents/index-status", headers=self.admin_headers)
        self.assertEqual(index_status.status_code, 200)
        self.assertTrue(index_status.json()["data"]["ready"])

        service_cls.return_value.set_index_configuration.return_value = {
            "changed": True,
            "reindex_required": True,
            "stale_documents": 1,
        }
        index_settings = self.client.put(
            "/documents/index-settings",
            headers=self.admin_headers,
            json={"chunk_size": 800, "chunk_overlap": 150, "chunking_strategy": "structure"},
        )
        self.assertEqual(index_settings.status_code, 200)
        service_cls.return_value.set_index_configuration.assert_called_with(
            chunk_size=800,
            chunk_overlap=150,
            chunking_strategy="structure",
        )

        service_cls.return_value.preview_document.return_value = {"id": 1}
        preview = self.client.get("/documents/1/preview", headers=self.admin_headers)
        self.assertEqual(preview.status_code, 200)

        service_cls.return_value.delete_document.return_value = False
        self.assertEqual(
            self.client.delete("/documents/1", headers=self.admin_headers).status_code,
            404,
        )

        service_cls.return_value.index_documents.return_value = {"total_chunks": 3}
        self.assertEqual(
            self.client.post("/documents/reindex", headers=self.admin_headers).status_code,
            200,
        )
        service_cls.return_value.reset_index.return_value = True
        self.assertEqual(
            self.client.post("/documents/reset-index", headers=self.admin_headers).status_code,
            200,
        )

    @patch("app.api.feedback.FeedbackService")
    def test_feedback_and_analytics_endpoints(self, service_cls):
        service_cls.return_value.create_feedback.return_value = {"rating": "up"}
        feedback = self.client.post(
            "/feedback",
            headers=self.user_headers,
            json={"chat_log_id": 1, "rating": "up", "comment": "Good"},
        )
        self.assertEqual(feedback.status_code, 200)

        service_cls.return_value.failed_question_analytics.return_value = {
            "bad_feedback": []
        }
        analytics = self.client.get(
            "/analytics/failed-questions", headers=self.admin_headers
        )
        self.assertEqual(analytics.status_code, 200)

        service_cls.return_value.clear_failed_question_analytics.return_value = {
            "total_deleted": 3
        }
        cleared = self.client.delete(
            "/analytics/failed-questions", headers=self.admin_headers
        )
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(cleared.json()["data"]["total_deleted"], 3)

        user_analytics = self.client.get(
            "/analytics/failed-questions", headers=self.user_headers
        )
        self.assertEqual(user_analytics.status_code, 403)
        user_clear = self.client.delete(
            "/analytics/failed-questions", headers=self.user_headers
        )
        self.assertEqual(user_clear.status_code, 403)

    @patch("app.api.evaluation.EvaluationService")
    def test_evaluation_endpoint(self, service_cls):
        service_cls.return_value.latest_evaluation.return_value = {"run_id": 1}
        latest = self.client.get("/evaluation/latest", headers=self.admin_headers)
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.json()["data"]["run_id"], 1)

        user_latest = self.client.get("/evaluation/latest", headers=self.user_headers)
        self.assertEqual(user_latest.status_code, 403)

        service_cls.return_value.load_evaluation_questions.return_value = [{"question": "Q"}]
        service_cls.return_value.run_evaluation.return_value = {"run_id": 1}
        response = self.client.post(
            "/evaluation/run",
            headers=self.admin_headers,
            files={"csv_file": ("evaluation.csv", b"question\nQ", "text/csv")},
            data={
                "retrieval_method": "hybrid",
                "reranker": "enabled",
                "chunking_strategy": "structure",
                "retrieval_profile": "auto",
                "answer_verification": "true",
                "benchmark_split": "holdout",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["run_id"], 1)
        service_cls.return_value.run_evaluation.assert_called_once()
        call_kwargs = service_cls.return_value.run_evaluation.call_args.kwargs
        self.assertEqual(call_kwargs["retrieval_profile"], "auto")
        self.assertTrue(call_kwargs["answer_verification"])
        self.assertEqual(call_kwargs["benchmark_split"], "holdout")

        bad = self.client.post(
            "/evaluation/run",
            headers=self.admin_headers,
            files={"csv_file": ("evaluation.txt", b"Q", "text/plain")},
        )
        self.assertEqual(bad.status_code, 400)

        service_cls.return_value.judge_semantic_correctness.return_value = {
            "run_id": 1,
            "semantic_answer_correctness": 0.9,
        }
        judged = self.client.post(
            "/evaluation/1/semantic-judge",
            headers=self.admin_headers,
        )
        self.assertEqual(judged.status_code, 200)
        self.assertEqual(judged.json()["data"]["semantic_answer_correctness"], 0.9)

    @patch("app.api.optimization.optimization_jobs")
    @patch("app.api.optimization.EvaluationService")
    def test_optimization_endpoints(self, service_cls, jobs):
        service_cls.return_value.load_evaluation_questions.return_value = [{"question": "Q"}]
        service_cls.return_value._validate_search_space.return_value = [
            (400, 50, 3, "similarity", "none", "auto")
        ]
        jobs.start.return_value = {"job_id": "job-1"}
        started = self.client.post(
            "/optimization/run",
            headers=self.admin_headers,
            files={"csv_file": ("evaluation.csv", b"question\nQ", "text/csv")},
            data={
                "chunk_sizes": "400",
                "chunk_overlaps": "50",
                "top_k_values": "3",
                "retrieval_methods": "similarity",
                "rerankers": "none",
                "chunking_strategies": "auto",
            },
        )
        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json()["job_id"], "job-1")

        jobs.get.return_value = {"status": "running"}
        self.assertEqual(
            self.client.get("/optimization/jobs/job-1", headers=self.admin_headers).status_code,
            200,
        )
        jobs.cancel.return_value = {"status": "cancelled"}
        self.assertEqual(
            self.client.post(
                "/optimization/jobs/job-1/cancel", headers=self.admin_headers
            ).status_code,
            200,
        )

        service_cls.return_value.apply_best_configuration.return_value = {
            "chunk_size": 400
        }
        applied = self.client.post(
            "/optimization/runs/1/apply-best", headers=self.admin_headers
        )
        self.assertEqual(applied.status_code, 200)


if __name__ == "__main__":
    unittest.main()
