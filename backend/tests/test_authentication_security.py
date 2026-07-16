import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.auth import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, create_access_token
from app.api.rate_limit import rate_limiter
from app.config import ADMIN_PASSWORD
from app.db.database import get_db
from app.main import app


class AuthenticationApiSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db] = lambda: MagicMock()
        cls.client = TestClient(app, raise_server_exceptions=False)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()

    def setUp(self):
        rate_limiter._events.clear()
        self.client.cookies.clear()

    def test_missing_token_returns_401_for_protected_endpoint(self):
        response = self.client.get("/auth/me")
        self.assertEqual(response.status_code, 401)

    def test_malformed_token_returns_401(self):
        response = self.client.get(
            "/auth/me",
            headers={"Authorization": "Bearer this-is-not-a-token"},
        )
        self.assertEqual(response.status_code, 401)

    def test_tampered_token_returns_401(self):
        token = create_access_token("user", session_id="tamper-test")
        payload, signature = token.split(".", 1)
        changed_first_character = "A" if signature[0] != "A" else "B"
        tampered = f"{payload}.{changed_first_character}{signature[1:]}"

        response = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {tampered}"},
        )
        self.assertEqual(response.status_code, 401)

    def test_expired_token_returns_401(self):
        token = create_access_token(
            "user",
            session_id="expired-test",
            expires_in_seconds=-1,
        )
        response = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 401)

    def test_invalid_role_token_returns_401(self):
        token = create_access_token("owner", session_id="invalid-role-test")
        response = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 401)

    def test_user_token_cannot_be_promoted_by_client_role_headers(self):
        token = create_access_token("user", session_id="spoofed-admin")
        response = self.client.get(
            "/documents/",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Role": "admin",
                "X-User-Role": "admin",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_wrong_admin_password_returns_401(self):
        response = self.client.post(
            "/auth/login",
            json={"role": "admin", "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 401)

    def test_login_uses_http_only_cookie_and_csrf_instead_of_returning_bearer_token(self):
        response = self.client.post(
            "/auth/login",
            json={"role": "admin", "password": ADMIN_PASSWORD},
        )
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("access_token", body)
        self.assertEqual(body["role"], "admin")
        self.assertTrue(body["csrf_token"])
        self.assertIn("docuquery_session", response.cookies)
        self.assertIn(CSRF_COOKIE_NAME, response.cookies)
        self.assertIn("httponly", response.headers.get("set-cookie", "").lower())

        session = self.client.get("/auth/me")
        self.assertEqual(session.status_code, 200)
        self.assertEqual(session.json()["role"], "admin")
        self.assertTrue(session.json()["csrf_token"])

    def test_cookie_authenticated_write_requires_valid_csrf_token(self):
        login = self.client.post(
            "/auth/login",
            json={"role": "admin", "password": ADMIN_PASSWORD},
        )
        self.assertEqual(login.status_code, 200)

        blocked = self.client.post("/auth/logout")
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.json()["detail"]["code"], "csrf_failed")

        current_csrf = self.client.cookies.get(CSRF_COOKIE_NAME)
        logged_out = self.client.post(
            "/auth/logout",
            headers={CSRF_HEADER_NAME: current_csrf},
        )
        self.assertEqual(logged_out.status_code, 200)
        self.assertEqual(self.client.get("/auth/me").status_code, 401)

    def test_admin_login_is_rate_limited_after_repeated_failures(self):
        for _ in range(5):
            response = self.client.post(
                "/auth/login",
                json={"role": "admin", "password": "wrong-password"},
            )
            self.assertEqual(response.status_code, 401)

        blocked = self.client.post(
            "/auth/login",
            json={"role": "admin", "password": "wrong-password"},
        )
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.json()["detail"]["code"], "rate_limit_exceeded")

    def test_client_logout_token_removal_results_in_backend_401(self):
        token = create_access_token("user", session_id="logout-test")
        authenticated = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        after_client_removes_token = self.client.get("/auth/me")

        self.assertEqual(authenticated.status_code, 200)
        self.assertEqual(after_client_removes_token.status_code, 401)

    def test_auth_me_returns_current_role_for_user_and_admin(self):
        for role in ("user", "admin"):
            with self.subTest(role=role):
                token = create_access_token(role, session_id=f"{role}-session")
                response = self.client.get(
                    "/auth/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["role"], role)


class ProductionAuthenticationConfigurationTests(unittest.TestCase):
    backend_root = Path(__file__).resolve().parents[1]

    def run_config_import(self, **values):
        environment = os.environ.copy()
        environment.update(values)
        return subprocess.run(
            [sys.executable, "-c", "import app.config"],
            cwd=self.backend_root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def assert_config_rejected(self, expected_message, **values):
        result = self.run_config_import(**values)
        output = f"{result.stdout}\n{result.stderr}"
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn(expected_message, output)

    def test_production_rejects_default_auth_secret(self):
        self.assert_config_rejected(
            "AUTH_SECRET_KEY",
            APP_ENV="production",
            AUTH_SECRET_KEY="change-this-development-secret",
            ADMIN_PASSWORD="strong-production-admin-password",
        )

    def test_production_rejects_weak_auth_secret(self):
        self.assert_config_rejected(
            "AUTH_SECRET_KEY",
            APP_ENV="production",
            AUTH_SECRET_KEY="short-secret",
            ADMIN_PASSWORD="strong-production-admin-password",
        )

    def test_production_rejects_default_admin_password(self):
        self.assert_config_rejected(
            "ADMIN_PASSWORD",
            APP_ENV="production",
            AUTH_SECRET_KEY="a-strong-production-secret-that-is-over-32-characters",
            ADMIN_PASSWORD="admin",
        )

    def test_production_rejects_empty_admin_password(self):
        self.assert_config_rejected(
            "ADMIN_PASSWORD",
            APP_ENV="production",
            AUTH_SECRET_KEY="a-strong-production-secret-that-is-over-32-characters",
            ADMIN_PASSWORD="",
        )

    def test_production_rejects_weak_admin_password(self):
        self.assert_config_rejected(
            "ADMIN_PASSWORD",
            APP_ENV="production",
            AUTH_SECRET_KEY="a-strong-production-secret-that-is-over-32-characters",
            ADMIN_PASSWORD="short",
        )

    def test_production_rejects_missing_provider_settings_encryption_key(self):
        self.assert_config_rejected(
            "PROVIDER_SETTINGS_ENCRYPTION_KEY",
            APP_ENV="production",
            AUTH_SECRET_KEY="a-strong-production-secret-that-is-over-32-characters",
            ADMIN_PASSWORD="strong-production-admin-password",
            PROVIDER_SETTINGS_ENCRYPTION_KEY="",
        )

    def test_development_allows_explicit_demo_defaults(self):
        result = self.run_config_import(
            APP_ENV="development",
            AUTH_SECRET_KEY="change-this-development-secret",
            ADMIN_PASSWORD="admin",
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
