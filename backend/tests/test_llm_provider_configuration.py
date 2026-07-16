import importlib
import os
import sys
import unittest
from unittest.mock import MagicMock, patch


PROVIDER_MODULES = [
    "app.rag.providers",
    "app.rag.generator",
    "app.rag.embeddings",
]


class LlmProviderConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()
        for key in list(os.environ):
            if (
                key.startswith("LLM_")
                or key.startswith("EMBEDDING_")
                or key
                in {
                    "OPENAI_API_KEY",
                    "OPENAI_MODEL",
                    "OPENAI_EMBEDDING_MODEL",
                    "OPENROUTER_API_KEY",
                    "GROQ_API_KEY",
                    "MISTRAL_API_KEY",
                    "GEMINI_API_KEY",
                    "GOOGLE_API_KEY",
                    "ANTHROPIC_API_KEY",
                    "TOGETHER_API_KEY",
                    "DEEPSEEK_API_KEY",
                    "XAI_API_KEY",
                }
            ):
                os.environ.pop(key, None)
        self.unload_provider_modules()
        self.saved_settings_patcher = patch(
            "app.services.provider_settings_service.load_runtime_provider_settings",
            return_value=None,
        )
        self.saved_settings_patcher.start()

    def tearDown(self):
        self.saved_settings_patcher.stop()
        os.environ.clear()
        os.environ.update(self.original_env)
        self.unload_provider_modules()

    def unload_provider_modules(self):
        for module_name in PROVIDER_MODULES:
            sys.modules.pop(module_name, None)

    def import_providers(self, **env):
        os.environ.update(env)
        self.unload_provider_modules()
        return importlib.import_module("app.rag.providers")

    def test_openrouter_chat_provider_uses_generic_api_key_and_default_base_url(self):
        providers = self.import_providers(
            LLM_PROVIDER="openrouter",
            LLM_API_KEY="openrouter-key",
            LLM_MODEL="anthropic/claude-3.5-sonnet",
        )

        settings = providers.get_chat_settings()

        self.assertEqual(settings.provider, "openrouter")
        self.assertEqual(settings.api_key, "openrouter-key")
        self.assertEqual(settings.model, "anthropic/claude-3.5-sonnet")
        self.assertEqual(settings.base_url, "https://openrouter.ai/api/v1")

    def test_gemini_chat_provider_uses_named_key_and_default_base_url(self):
        providers = self.import_providers(
            LLM_PROVIDER="gemini",
            GEMINI_API_KEY="gemini-key",
            LLM_MODEL="gemini-2.5-flash",
        )

        settings = providers.get_chat_settings()

        self.assertEqual(settings.provider, "gemini")
        self.assertEqual(settings.api_key, "gemini-key")
        self.assertEqual(settings.model, "gemini-2.5-flash")
        self.assertEqual(settings.base_url, "https://generativelanguage.googleapis.com/v1beta/openai")

    def test_gemini_provider_accepts_google_api_key_alias(self):
        providers = self.import_providers(
            LLM_PROVIDER="gemini",
            GOOGLE_API_KEY="google-key",
        )

        settings = providers.get_chat_settings()

        self.assertEqual(settings.api_key, "google-key")

    def test_anthropic_chat_provider_uses_named_key(self):
        providers = self.import_providers(
            LLM_PROVIDER="anthropic",
            ANTHROPIC_API_KEY="anthropic-key",
            LLM_MODEL="claude-sonnet-4-5",
        )

        settings = providers.get_chat_settings()

        self.assertEqual(settings.provider, "anthropic")
        self.assertEqual(settings.api_key, "anthropic-key")
        self.assertEqual(settings.model, "claude-sonnet-4-5")
        self.assertIsNone(settings.base_url)

    def test_anthropic_is_not_supported_for_embeddings(self):
        providers = self.import_providers(
            EMBEDDING_PROVIDER="anthropic",
            ANTHROPIC_API_KEY="anthropic-key",
            EMBEDDING_MODEL="claude-sonnet-4-5",
        )

        with self.assertRaisesRegex(RuntimeError, "does not provide embeddings"):
            providers.get_embedding_settings()

    def test_custom_openai_compatible_provider_requires_base_url(self):
        providers = self.import_providers(
            LLM_PROVIDER="openai-compatible",
            LLM_API_KEY="custom-key",
            LLM_MODEL="custom-chat-model",
        )

        with self.assertRaisesRegex(RuntimeError, "LLM_BASE_URL"):
            providers.get_chat_settings()

    def test_custom_openai_compatible_provider_accepts_base_url(self):
        providers = self.import_providers(
            LLM_PROVIDER="openai-compatible",
            LLM_API_KEY="custom-key",
            LLM_BASE_URL="https://llm.example.com/v1",
            LLM_MODEL="custom-chat-model",
        )

        settings = providers.get_chat_settings()

        self.assertEqual(settings.api_key, "custom-key")
        self.assertEqual(settings.base_url, "https://llm.example.com/v1")
        self.assertEqual(settings.model, "custom-chat-model")

    def test_legacy_openai_environment_still_works(self):
        providers = self.import_providers(OPENAI_API_KEY="openai-key")

        chat = providers.get_chat_settings()
        embeddings = providers.get_embedding_settings()

        self.assertEqual(chat.provider, "openai")
        self.assertEqual(chat.api_key, "openai-key")
        self.assertEqual(chat.model, "gpt-4o-mini")
        self.assertEqual(embeddings.provider, "openai")
        self.assertEqual(embeddings.api_key, "openai-key")
        self.assertEqual(embeddings.model, "text-embedding-3-small")

    def test_missing_chat_key_mentions_generic_llm_api_key(self):
        providers = self.import_providers(LLM_PROVIDER="groq", LLM_MODEL="llama-3.1-8b-instant")

        with self.assertRaisesRegex(RuntimeError, "LLM_API_KEY"):
            providers.get_chat_settings()

    def test_provider_specific_api_key_is_supported(self):
        providers = self.import_providers(
            LLM_PROVIDER="groq",
            GROQ_API_KEY="groq-provider-key",
            LLM_MODEL="llama-3.1-8b-instant",
        )

        settings = providers.get_chat_settings()

        self.assertEqual(settings.api_key, "groq-provider-key")

    def test_saved_admin_provider_settings_override_environment(self):
        providers = self.import_providers(
            LLM_PROVIDER="openai",
            LLM_API_KEY="env-key",
            LLM_MODEL="env-model",
        )

        with patch(
            "app.services.provider_settings_service.load_runtime_provider_settings",
            return_value={
                "provider": "groq",
                "api_key": "saved-key",
                "model": "saved-model",
                "base_url": "https://api.groq.com/openai/v1",
            },
        ):
            settings = providers.get_chat_settings()

        self.assertEqual(settings.provider, "groq")
        self.assertEqual(settings.api_key, "saved-key")
        self.assertEqual(settings.model, "saved-model")
        self.assertEqual(settings.base_url, "https://api.groq.com/openai/v1")

    def test_answer_generator_uses_resolved_chat_provider_client(self):
        self.import_providers(
            LLM_PROVIDER="groq",
            LLM_API_KEY="groq-key",
            LLM_MODEL="llama-3.1-8b-instant",
        )
        generator = importlib.import_module("app.rag.generator")

        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content="Grounded answer"))]

        with patch("app.rag.providers.OpenAI") as openai_cls:
            client = openai_cls.return_value
            client.chat.completions.create.return_value = response

            answer = generator.AnswerGenerator.generate("Question?", "Context")

        self.assertEqual(answer, "Grounded answer")
        openai_cls.assert_called_once_with(
            api_key="groq-key",
            base_url="https://api.groq.com/openai/v1",
        )
        self.assertEqual(
            client.chat.completions.create.call_args.kwargs["model"],
            "llama-3.1-8b-instant",
        )

    def test_answer_generator_uses_native_anthropic_messages_api(self):
        self.import_providers(
            LLM_PROVIDER="anthropic",
            ANTHROPIC_API_KEY="anthropic-key",
            LLM_MODEL="claude-sonnet-4-5",
        )
        generator = importlib.import_module("app.rag.generator")

        with patch("app.rag.generator._post_anthropic_json") as post_json, patch(
            "app.rag.providers.OpenAI"
        ) as openai_cls:
            post_json.return_value = {"content": [{"type": "text", "text": "Grounded Claude answer"}]}

            answer = generator.AnswerGenerator.generate("Question?", "Context")

        self.assertEqual(answer, "Grounded Claude answer")
        openai_cls.assert_not_called()
        self.assertEqual(post_json.call_args.args[0], "https://api.anthropic.com/v1/messages")
        self.assertEqual(post_json.call_args.args[1], "anthropic-key")
        self.assertEqual(post_json.call_args.args[2]["model"], "claude-sonnet-4-5")

    def test_embeddings_generator_uses_independent_embedding_provider_client(self):
        self.import_providers(
            EMBEDDING_PROVIDER="openai-compatible",
            EMBEDDING_API_KEY="embedding-key",
            EMBEDDING_BASE_URL="https://embeddings.example.com/v1",
            EMBEDDING_MODEL="embedding-model",
        )
        embeddings = importlib.import_module("app.rag.embeddings")

        item = MagicMock(index=0, embedding=[0.1, 0.2, 0.3])
        response = MagicMock(data=[item])

        with patch("app.rag.providers.OpenAI") as openai_cls:
            client = openai_cls.return_value
            client.embeddings.create.return_value = response

            vectors = embeddings.EmbeddingsGenerator.embed_texts(["hello"])

        self.assertEqual(vectors, [[0.1, 0.2, 0.3]])
        openai_cls.assert_called_once_with(
            api_key="embedding-key",
            base_url="https://embeddings.example.com/v1",
        )
        self.assertEqual(
            client.embeddings.create.call_args.kwargs["model"],
            "embedding-model",
        )

    def test_ollama_embeddings_use_native_batch_endpoint(self):
        self.import_providers(
            EMBEDDING_PROVIDER="ollama",
            EMBEDDING_MODEL="nomic-embed-text",
        )
        embeddings = importlib.import_module("app.rag.embeddings")

        with patch("app.rag.embeddings._post_ollama_json") as post_json, patch(
            "app.rag.providers.OpenAI"
        ) as openai_cls:
            post_json.return_value = {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}

            vectors = embeddings.EmbeddingsGenerator.embed_texts(["hello", "world"])

        self.assertEqual(vectors, [[0.1, 0.2], [0.3, 0.4]])
        post_json.assert_called_once_with(
            "http://localhost:11434/api/embed",
            {"model": "nomic-embed-text", "input": ["hello", "world"]},
        )
        openai_cls.assert_not_called()

    def test_gemini_embeddings_use_native_batch_endpoint(self):
        self.import_providers(
            EMBEDDING_PROVIDER="gemini",
            GEMINI_API_KEY="gemini-key",
            EMBEDDING_MODEL="gemini-embedding-001",
        )
        embeddings = importlib.import_module("app.rag.embeddings")

        with patch("app.rag.embeddings._post_gemini_json") as post_json, patch(
            "app.rag.providers.OpenAI"
        ) as openai_cls:
            post_json.return_value = {
                "embeddings": [
                    {"values": [0.1, 0.2]},
                    {"values": [0.3, 0.4]},
                ]
            }

            vectors = embeddings.EmbeddingsGenerator.embed_texts(["hello", "world"])

        self.assertEqual(vectors, [[0.1, 0.2], [0.3, 0.4]])
        post_json.assert_called_once()
        self.assertEqual(
            post_json.call_args.args[0],
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents",
        )
        self.assertEqual(post_json.call_args.args[1], "gemini-key")
        self.assertEqual(
            [request["content"]["parts"][0]["text"] for request in post_json.call_args.args[2]["requests"]],
            ["hello", "world"],
        )
        openai_cls.assert_not_called()

    def test_ollama_embeddings_are_batched_for_large_document_sets(self):
        self.import_providers(
            EMBEDDING_PROVIDER="ollama",
            EMBEDDING_MODEL="nomic-embed-text",
        )
        embeddings = importlib.import_module("app.rag.embeddings")
        texts = [f"chunk {index}" for index in range(17)]

        with patch("app.rag.embeddings._post_ollama_json") as post_json:
            post_json.side_effect = [
                {"embeddings": [[float(index)] for index in range(16)]},
                {"embeddings": [[16.0]]},
            ]

            vectors = embeddings.EmbeddingsGenerator.embed_texts(texts)

        self.assertEqual(vectors, [[float(index)] for index in range(17)])
        self.assertEqual(post_json.call_count, 2)
        self.assertEqual(len(post_json.call_args_list[0].args[1]["input"]), 16)
        self.assertEqual(len(post_json.call_args_list[1].args[1]["input"]), 1)


if __name__ == "__main__":
    unittest.main()
