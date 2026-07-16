import csv
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Document, EvaluationRun
from app.services.evaluation_service import EvaluationService


class FakeDocumentService:
    def __init__(self):
        self.index_calls = []
        self.active_configuration = {
            "chunk_size": 800,
            "chunk_overlap": 100,
            "chunking_strategy": "auto",
        }
        self.reset_calls = 0

    def ensure_index_configuration(self, chunk_size, chunk_overlap, chunking_strategy="auto"):
        self.index_calls.append((chunk_size, chunk_overlap, chunking_strategy))
        return {"reindexed": False}

    def index_documents(self, chunk_size, chunk_overlap, chunking_strategy="auto", reset=True):
        self.index_calls.append((chunk_size, chunk_overlap, chunking_strategy))
        return {"reindexed": True}

    def get_active_configuration(self):
        return self.active_configuration

    def reset_index(self):
        self.reset_calls += 1
        return True


class FakeRAG:
    def run(
        self,
        question,
        top_k,
        retrieval_method,
        reranker="none",
        prompt_variant="grounded_complete",
        retrieval_profile="manual",
        answer_verification=False,
        question_type=None,
        show_debug=False,
    ):
        if "unknown" in question:
            return {
                "answer": "I could not find this information in the uploaded documents.",
                "sources": [],
                "retrieved_chunks": [],
                "latency_seconds": 0.2,
            }
        return {
            "answer": "Employees receive 20 days of annual leave.",
            "sources": [
                {
                    "filename": "expected.pdf",
                    "page": 2,
                    "locator_label": "Page 2",
                    "source_type": "pdf",
                    "content_unit_count": 2,
                }
            ],
            "retrieved_chunks": [
                {
                    "filename": "expected.pdf",
                    "page": 2,
                    "locator_label": "Page 2",
                    "full_text": "Employees receive 20 days of annual leave.",
                }
            ],
            "latency_seconds": 0.1,
        }


class EvaluationServiceTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()
        self.session.add(
            Document(
                filename="expected.pdf",
                original_filename="expected.pdf",
                file_path="expected.pdf",
                document_type="pdf",
                page_count=2,
                content_unit_count=2,
                status="indexed",
                chunk_count=1,
            )
        )
        self.session.commit()

        self.service = EvaluationService(self.session)
        self.service.doc_service = FakeDocumentService()
        self.service.rag = FakeRAG()
        self.questions = [
            {
                "question": "How much annual leave do employees receive?",
                "question_type": "policy_procedure",
                "reference_answer": "Employees receive 20 days of annual leave.",
                "expected_source": "expected.pdf",
                "expected_page": 2,
                "expected_locator": None,
            },
            {
                "question": "What unknown fact is requested?",
                "question_type": "unanswerable",
                "reference_answer": "The answer is not available in the provided documents.",
                "expected_source": None,
                "expected_page": None,
                "expected_locator": None,
            },
        ]

    def tearDown(self):
        self.session.close()

    def test_evaluation_returns_complete_metrics(self):
        result = self.service.run_evaluation(
            questions=self.questions,
            chunk_size=800,
            chunk_overlap=100,
            top_k=5,
            retrieval_method="similarity",
        )

        self.assertEqual(result["total_questions"], 2)
        self.assertEqual(result["answerable_questions"], 1)
        self.assertEqual(result["unanswerable_questions"], 1)
        self.assertEqual(result["source_hit_rate"], 1.0)
        self.assertEqual(result["refusal_accuracy"], 1.0)
        self.assertEqual(result["answer_correctness"], 1.0)
        self.assertEqual(result["faithfulness"], 1.0)
        self.assertGreater(result["context_relevance"], 0)
        self.assertEqual(result["prompt_variant"], "grounded_complete")
        self.assertEqual(result["retrieval_profile"], "manual")
        self.assertFalse(result["answer_verification"])
        self.assertEqual(result["benchmark_split"], "known")
        self.assertEqual(len(result["results"]), 2)
        self.assertIn("generated_answer", result["results"][0])
        self.assertIn("correctness_explanation", result["results"][0])
        self.assertEqual(result["results"][0]["prompt_variant"], "grounded_complete")
        self.assertEqual(result["results"][0]["retrieval_profile"], "manual")
        self.assertEqual(self.service.doc_service.index_calls, [(800, 100, "auto")])

    def test_auto_retrieval_profile_and_answer_verification_metadata_are_stored(self):
        calls = []

        class RecordingRAG(FakeRAG):
            def run(self, *args, **kwargs):
                calls.append(kwargs)
                return super().run(*args, **kwargs)

        self.service.rag = RecordingRAG()
        result = self.service.run_evaluation(
            questions=self.questions,
            chunk_size=800,
            chunk_overlap=100,
            top_k=5,
            retrieval_method="similarity",
            retrieval_profile="auto",
            answer_verification=True,
            benchmark_split="holdout",
        )

        self.assertEqual(result["benchmark_split"], "holdout")
        self.assertEqual(result["retrieval_profile"], "auto")
        self.assertTrue(result["answer_verification"])
        self.assertEqual(calls[0]["retrieval_profile"], "auto")
        self.assertTrue(calls[0]["answer_verification"])
        self.assertEqual(calls[0]["question_type"], "policy_procedure")
        self.assertEqual(result["results"][0]["retrieval_profile"], "auto")

    def test_source_hit_supports_expected_locator_for_non_pdf_sources(self):
        sources = [{"filename": "support.xlsx", "locator_label": "Support, Rows 2-10"}]
        question_data = {
            "expected_source": "support.xlsx",
            "expected_page": None,
            "expected_locator": "Support, Rows 2-10",
        }
        self.assertTrue(self.service._source_hit(sources, question_data))

    def test_optimization_indexes_once_per_configuration_and_exports_ranking(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.service._evaluation_directory = lambda: Path(temp_dir)
            result = self.service.run_optimization_experiments(
                questions=self.questions,
                chunk_sizes=[400, 800],
                chunk_overlaps=[50],
                top_k_values=[3],
                retrieval_methods=["similarity"],
                chunking_strategies=["auto"],
            )

            self.assertEqual(result["total_configurations"], 2)
            self.assertEqual(
                self.service.doc_service.index_calls,
                [(400, 50, "auto"), (800, 50, "auto"), (800, 100, "auto")],
            )
            self.assertEqual([row["rank"] for row in result["results"]], [1, 2])
            self.assertTrue(all(row["total_questions"] == 2 for row in result["results"]))
            self.assertEqual(
                result["active_configuration"],
                {"chunk_size": 800, "chunk_overlap": 100, "chunking_strategy": "auto"},
            )

            with open(result["results_path"], newline="", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(len(rows), 2)
            self.assertIn("retrieval_method", rows[0])
            self.assertIn("chunking_strategy", rows[0])
            self.assertIn("prompt_variant", rows[0])
            self.assertIn("total_questions", rows[0])
            self.assertIn("answer_correctness", rows[0])
            self.assertEqual(rows[0]["prompt_variant"], "grounded_complete")

    def test_csv_accepts_answerable_categories_and_unanswerable_none_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            valid_path = Path(temp_dir) / "valid.csv"
            valid_path.write_text(
                "question,reference_answer,expected_source,expected_page,question_type\n"
                "How much leave?,20 days,expected.pdf,2,policy_procedure\n"
                "What is the CEO phone number?,The answer is not available in the provided documents.,none,none,unanswerable\n",
                encoding="utf-8",
            )
            questions = self.service.load_evaluation_questions(str(valid_path))
            self.assertEqual(questions[0]["reference_answer"], "20 days")
            self.assertEqual(questions[0]["question_type"], "policy_procedure")
            self.assertIsNone(questions[1]["expected_source"])
            self.assertIn("not available", questions[1]["reference_answer"])

            invalid_path = Path(temp_dir) / "invalid.csv"
            invalid_path.write_text(
                "question,reference_answer,expected_source,expected_page,question_type\n"
                "How much leave?,,expected.pdf,2,policy_procedure\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "reference_answer"):
                self.service.load_evaluation_questions(str(invalid_path))

    def test_csv_accepts_expected_locator_without_expected_page(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            valid_path = Path(temp_dir) / "valid_locator.csv"
            valid_path.write_text(
                "question,reference_answer,expected_source,expected_page,question_type,expected_locator\n"
                "Which section?,Support guidance,expected.pdf,,customer_support_behavior,Page 2\n",
                encoding="utf-8",
            )
            questions = self.service.load_evaluation_questions(str(valid_path))
            self.assertEqual(questions[0]["expected_locator"], "Page 2")

    def test_csv_missing_columns_reports_official_header(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid_path = Path(temp_dir) / "missing_columns.csv"
            invalid_path.write_text(
                "question,expected_source,expected_page,question_type\n"
                "How much leave?,expected.pdf,2,policy_procedure\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError,
                "question,reference_answer,expected_source,expected_page,question_type",
            ):
                self.service.load_evaluation_questions(str(invalid_path))

    def test_csv_rejects_unanswerable_rows_with_expected_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid_path = Path(temp_dir) / "unanswerable_with_source.csv"
            invalid_path.write_text(
                "question,reference_answer,expected_source,expected_page,question_type\n"
                "What is the CEO phone number?,Private number,expected.pdf,2,unanswerable\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unanswerable questions must leave"):
                self.service.load_evaluation_questions(str(invalid_path))

    def test_csv_rejects_unknown_expected_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid_path = Path(temp_dir) / "unknown_source.csv"
            invalid_path.write_text(
                "question,reference_answer,expected_source,expected_page,question_type\n"
                "How much leave?,20 days,missing.pdf,2,policy_procedure\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "exactly match an uploaded document filename"):
                self.service.load_evaluation_questions(str(invalid_path))

    def test_apply_best_configuration_rebuilds_active_index(self):
        result = self.service.run_optimization_experiments(
            questions=self.questions,
            chunk_sizes=[400],
            chunk_overlaps=[50],
            top_k_values=[3],
            retrieval_methods=["similarity"],
            chunking_strategies=["auto"],
        )
        applied = self.service.apply_best_configuration(result["run_id"])
        self.assertEqual(applied["chunk_size"], 400)
        self.assertEqual(applied["chunk_overlap"], 50)
        self.assertEqual(applied["chunking_strategy"], "auto")
        self.assertEqual(applied["prompt_variant"], "grounded_complete")
        self.assertEqual(self.service.doc_service.index_calls[-1], (400, 50, "auto"))

    def test_inline_semantic_judge_and_prompt_variant_are_stored(self):
        self.service.quality.semantic_answer_correctness = lambda **kwargs: {
            "score": 0.9,
            "verdict": "correct",
            "explanation": "Same meaning.",
        }
        result = self.service.run_evaluation(
            questions=self.questions,
            chunk_size=800,
            chunk_overlap=100,
            top_k=5,
            retrieval_method="similarity",
            prompt_variant="policy_procedure",
            semantic_judge=True,
        )

        self.assertEqual(result["semantic_answer_correctness"], 0.9)
        self.assertEqual(result["prompt_variant"], "policy_procedure")
        self.assertEqual(result["results"][0]["semantic_verdict"], "correct")
        self.assertEqual(result["results"][0]["prompt_variant"], "policy_procedure")

    def test_latest_evaluation_skips_incomplete_run_shells(self):
        completed = self.service.run_evaluation(
            questions=self.questions,
            chunk_size=800,
            chunk_overlap=100,
            top_k=5,
            retrieval_method="similarity",
        )
        self.session.add(
            EvaluationRun(
                total_questions=40,
                answerable_questions=36,
                unanswerable_questions=4,
                source_hit_rate=0,
                refusal_accuracy=0,
                answer_correctness=0,
                semantic_answer_correctness=None,
                faithfulness=0,
                context_relevance=0,
                average_latency=0,
            )
        )
        self.session.commit()

        latest = self.service.latest_evaluation()
        self.assertEqual(latest["run_id"], completed["run_id"])

    def test_optimization_with_no_previous_index_resets_after_run(self):
        self.service.doc_service.active_configuration = None
        result = self.service.run_optimization_experiments(
            questions=self.questions,
            chunk_sizes=[400],
            chunk_overlaps=[50],
            top_k_values=[3],
            retrieval_methods=["similarity"],
            chunking_strategies=["auto"],
        )
        self.assertIsNone(result["active_configuration"])
        self.assertEqual(self.service.doc_service.reset_calls, 1)

    def test_invalid_overlap_combination_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invalid combinations"):
            self.service.run_optimization_experiments(
                questions=self.questions,
                chunk_sizes=[100],
                chunk_overlaps=[100],
                top_k_values=[3],
                retrieval_methods=["similarity"],
                chunking_strategies=["auto"],
            )

    def test_optimization_safety_limits_top_k_and_configuration_count(self):
        with self.assertRaisesRegex(ValueError, "top_k_values"):
            self.service.run_optimization_experiments(
                questions=self.questions,
                chunk_sizes=[400],
                chunk_overlaps=[50],
                top_k_values=[999],
                retrieval_methods=["similarity"],
                chunking_strategies=["auto"],
            )
        with self.assertRaisesRegex(ValueError, "limited"):
            self.service.run_optimization_experiments(
                questions=self.questions,
                chunk_sizes=list(range(400, 1000, 10)),
                chunk_overlaps=[10],
                top_k_values=[3],
                retrieval_methods=["similarity"],
                chunking_strategies=["auto"],
            )


if __name__ == "__main__":
    unittest.main()
