import time
import unittest
from unittest.mock import patch

from app.services.optimization_jobs import OptimizationJobManager


class FakeSession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class SuccessfulEvaluationService:
    def __init__(self, db):
        self.db = db

    def run_optimization_experiments(self, progress_callback, cancel_check, **payload):
        progress_callback(1, 2)
        progress_callback(2, 2)
        return {"run_id": 10, "results": [{"rank": 1}]}


class CancellableEvaluationService:
    def __init__(self, db):
        self.db = db

    def run_optimization_experiments(self, progress_callback, cancel_check, **payload):
        for completed in range(1, 101):
            if cancel_check():
                break
            progress_callback(completed, 100)
            time.sleep(0.005)
        return {"run_id": 11, "results": []}


class OptimizationJobManagerTests(unittest.TestCase):
    def test_background_job_reports_progress_and_result(self):
        session = FakeSession()
        manager = OptimizationJobManager()
        with patch("app.services.optimization_jobs.SessionLocal", return_value=session), patch(
            "app.services.optimization_jobs.EvaluationService",
            SuccessfulEvaluationService,
        ):
            job = manager.start({}, total_configurations=2)
            completed = self._wait_for_terminal(manager, job["job_id"])

        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["completed_configurations"], 2)
        self.assertEqual(completed["result"]["run_id"], 10)
        self.assertTrue(session.closed)

    def test_background_job_can_be_cancelled(self):
        session = FakeSession()
        manager = OptimizationJobManager()
        with patch("app.services.optimization_jobs.SessionLocal", return_value=session), patch(
            "app.services.optimization_jobs.EvaluationService",
            CancellableEvaluationService,
        ):
            job = manager.start({}, total_configurations=100)
            manager.cancel(job["job_id"])
            cancelled = self._wait_for_terminal(manager, job["job_id"])

        self.assertEqual(cancelled["status"], "cancelled")
        self.assertTrue(cancelled["cancel_requested"])
        self.assertTrue(session.closed)

    @staticmethod
    def _wait_for_terminal(manager, job_id):
        for _ in range(200):
            job = manager.get(job_id)
            if job["status"] in {"completed", "cancelled", "failed"}:
                return job
            time.sleep(0.005)
        raise AssertionError("Background job did not reach a terminal state")


if __name__ == "__main__":
    unittest.main()
