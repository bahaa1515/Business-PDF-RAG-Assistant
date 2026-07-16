import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, create_access_token
from app.api.rate_limit import rate_limiter
from app.config import ADMIN_PASSWORD
from app.db.database import get_db
from app.db.models import Base, Document, ProviderSetting
from app.main import app
from app.services.provider_settings_service import (
    MASKED_SECRET,
    ProviderSettingsError,
    ProviderSettingsService,
    decrypt_secret,
    load_runtime_provider_settings,
)


try:
    import cryptography  # noqa: F401

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False


class ProviderSettingsSecurityTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        self.db = self.Session()
        rate_limiter._events.clear()

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        rate_limiter._events.clear()

    def override_db(self):
        def _get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = _get_db

    @unittest.skipUnless(CRYPTOGRAPHY_AVAILABLE, "cryptography is not installed in the local test venv")
    def test_provider_settings_encrypts_and_masks_api_keys(self):
        service = ProviderSettingsService(self.db)
        public = service.update_settings(
            {
                "llm": {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "api_key": "sk-test-secret",
                }
            }
        )

        row = self.db.query(ProviderSetting).filter_by(service_name="llm").one()

        self.assertNotIn("sk-test-secret", row.encrypted_api_key)
        self.assertEqual(decrypt_secret(row.encrypted_api_key), "sk-test-secret")
        self.assertTrue(public["llm"]["api_key_set"])
        self.assertEqual(public["llm"]["api_key_display"], MASKED_SECRET)
        self.assertNotIn("sk-test-secret", str(public))

    @unittest.skipUnless(CRYPTOGRAPHY_AVAILABLE, "cryptography is not installed in the local test venv")
    def test_masked_placeholder_cannot_be_saved_as_real_key(self):
        service = ProviderSettingsService(self.db)

        with self.assertRaises(ProviderSettingsError):
            service.update_settings(
                {
                    "llm": {
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                        "api_key": MASKED_SECRET,
                    }
                }
            )

    @unittest.skipUnless(CRYPTOGRAPHY_AVAILABLE, "cryptography is not installed in the local test venv")
    def test_provider_or_base_url_change_requires_new_or_cleared_key(self):
        service = ProviderSettingsService(self.db)
        service.update_settings(
            {
                "llm": {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "api_key": "sk-original-secret",
                }
            }
        )

        updated_model = service.update_settings(
            {
                "llm": {
                    "provider": "openai",
                    "model": "gpt-4o",
                }
            }
        )
        self.assertEqual(updated_model["llm"]["model"], "gpt-4o")

        with self.assertRaisesRegex(ProviderSettingsError, "requires re-entering"):
            service.update_settings(
                {
                    "llm": {
                        "provider": "groq",
                        "model": "llama-3.1-8b-instant",
                    }
                }
            )

        service.update_settings(
            {
                "embedding": {
                    "provider": "custom",
                    "model": "embed-model",
                    "base_url": "https://provider-a.example.com/v1",
                    "api_key": "sk-custom-secret",
                }
            }
        )
        with self.assertRaisesRegex(ProviderSettingsError, "requires re-entering"):
            service.update_settings(
                {
                    "embedding": {
                        "provider": "custom",
                        "model": "embed-model",
                        "base_url": "https://provider-b.example.com/v1",
                    }
                }
            )

    @unittest.skipUnless(CRYPTOGRAPHY_AVAILABLE, "cryptography is not installed in the local test venv")
    def test_provider_settings_audit_log_does_not_include_raw_key(self):
        service = ProviderSettingsService(self.db)

        with self.assertLogs("app.security.provider_settings", level="INFO") as logs:
            service.update_settings(
                {
                    "llm": {
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                        "api_key": "sk-audit-secret",
                    }
                },
                audit_context={
                    "admin_session": "audit-admin",
                    "client_ip": "127.0.0.1",
                },
            )

        log_output = "\n".join(logs.output)
        self.assertIn("provider_settings_changed", log_output)
        self.assertIn("audit-admin", log_output)
        self.assertNotIn("sk-audit-secret", log_output)

    @unittest.skipUnless(CRYPTOGRAPHY_AVAILABLE, "cryptography is not installed in the local test venv")
    def test_provider_settings_api_is_admin_only_and_never_returns_raw_key(self):
        self.override_db()
        client = TestClient(app)
        user_headers = {
            "Authorization": f"Bearer {create_access_token('user', session_id='settings-user')}"
        }
        admin_headers = {
            "Authorization": f"Bearer {create_access_token('admin', session_id='settings-admin')}"
        }

        user_response = client.get("/admin/provider-settings/", headers=user_headers)
        self.assertEqual(user_response.status_code, 403)

        saved = client.put(
            "/admin/provider-settings/",
            headers=admin_headers,
            json={
                "llm": {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "api_key": "sk-admin-secret",
                },
                "embedding": {
                    "provider": "openai",
                    "model": "text-embedding-3-small",
                    "api_key": "sk-embed-secret",
                },
            },
        )

        self.assertEqual(saved.status_code, 200)
        body = saved.json()
        self.assertEqual(body["data"]["llm"]["api_key_display"], MASKED_SECRET)
        self.assertEqual(body["data"]["embedding"]["api_key_display"], MASKED_SECRET)
        self.assertNotIn("sk-admin-secret", str(body))
        self.assertNotIn("sk-embed-secret", str(body))

        fetched = client.get("/admin/provider-settings/", headers=admin_headers)
        self.assertEqual(fetched.status_code, 200)
        self.assertNotIn("sk-admin-secret", str(fetched.json()))

    @unittest.skipUnless(CRYPTOGRAPHY_AVAILABLE, "cryptography is not installed in the local test venv")
    def test_cookie_authenticated_provider_settings_write_requires_csrf(self):
        self.override_db()
        client = TestClient(app)
        login = client.post(
            "/auth/login",
            json={"role": "admin", "password": ADMIN_PASSWORD},
        )
        self.assertEqual(login.status_code, 200)
        payload = {
            "llm": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "api_key": "sk-cookie-secret",
            }
        }

        blocked = client.put("/admin/provider-settings/", json=payload)
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.json()["detail"]["code"], "csrf_failed")

        csrf_token = client.cookies.get(CSRF_COOKIE_NAME)
        saved = client.put(
            "/admin/provider-settings/",
            headers={CSRF_HEADER_NAME: csrf_token},
            json=payload,
        )
        self.assertEqual(saved.status_code, 200)
        self.assertNotIn("sk-cookie-secret", str(saved.json()))

    def test_provider_settings_write_endpoint_is_rate_limited(self):
        self.override_db()
        client = TestClient(app)
        headers = {
            "Authorization": f"Bearer {create_access_token('admin', session_id='rate-limited-settings')}"
        }
        payload = {
            "llm": {
                "provider": "ollama",
                "model": "llama3",
                "clear_api_key": True,
            }
        }

        for _ in range(20):
            response = client.put("/admin/provider-settings/", headers=headers, json=payload)
            self.assertEqual(response.status_code, 200)

        blocked = client.put("/admin/provider-settings/", headers=headers, json=payload)
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.json()["detail"]["code"], "rate_limit_exceeded")

    @unittest.skipUnless(CRYPTOGRAPHY_AVAILABLE, "cryptography is not installed in the local test venv")
    def test_embedding_provider_change_marks_indexed_documents_for_reindex(self):
        document = Document(
            filename="stored.pdf",
            original_filename="business-policy.pdf",
            file_path="/tmp/business-policy.pdf",
            document_type="pdf",
            page_count=1,
            content_unit_count=1,
            chunk_count=3,
            status="indexed",
            chunk_size=800,
            chunk_overlap=100,
            chunking_strategy="structure",
        )
        self.db.add(document)
        self.db.commit()

        service = ProviderSettingsService(self.db)
        public = service.update_settings(
            {
                "embedding": {
                    "provider": "gemini",
                    "model": "gemini-embedding-001",
                    "api_key": "gemini-secret",
                }
            }
        )

        self.db.refresh(document)
        self.assertEqual(document.status, "needs_reindex")
        self.assertTrue(public["reindex_required"])

    def test_anthropic_is_not_allowed_as_embedding_provider(self):
        service = ProviderSettingsService(self.db)

        with self.assertRaisesRegex(ProviderSettingsError, "LLM provider only"):
            service.update_settings(
                {
                    "embedding": {
                        "provider": "anthropic",
                        "model": "claude-sonnet-4-5",
                        "api_key": "anthropic-secret",
                    }
                }
            )

    def test_saved_ollama_settings_resolve_default_base_url_without_key(self):
        service = ProviderSettingsService(self.db)
        public = service.update_settings(
            {
                "llm": {
                    "provider": "ollama",
                    "model": "qwen2.5:7b-instruct",
                    "clear_api_key": True,
                },
                "embedding": {
                    "provider": "ollama",
                    "model": "nomic-embed-text",
                    "clear_api_key": True,
                },
            }
        )

        self.assertEqual(public["llm"]["base_url"], "http://localhost:11434/v1")
        self.assertFalse(public["llm"]["api_key_set"])
        self.assertEqual(public["embedding"]["base_url"], "http://localhost:11434/v1")
        self.assertFalse(public["embedding"]["api_key_set"])

        with patch("app.services.provider_settings_service.SessionLocal", return_value=self.db):
            llm_runtime = load_runtime_provider_settings("LLM")
            embedding_runtime = load_runtime_provider_settings("EMBEDDING")

        self.assertEqual(llm_runtime["api_key"], "ollama")
        self.assertEqual(llm_runtime["base_url"], "http://localhost:11434/v1")
        self.assertEqual(embedding_runtime["api_key"], "ollama")
        self.assertEqual(embedding_runtime["base_url"], "http://localhost:11434/v1")


if __name__ == "__main__":
    unittest.main()
