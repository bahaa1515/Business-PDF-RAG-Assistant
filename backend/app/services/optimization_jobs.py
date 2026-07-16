"""In-memory background optimization job coordinator."""
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict

from app.db.database import SessionLocal
from app.services.evaluation_service import EvaluationService


class OptimizationJobManager:
    def __init__(self):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def start(self, payload: Dict[str, Any], total_configurations: int) -> Dict[str, Any]:
        job_id = uuid.uuid4().hex
        job = {
            "job_id": job_id,
            "status": "queued",
            "completed_configurations": 0,
            "total_configurations": total_configurations,
            "cancel_requested": False,
            "result": None,
            "error": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._jobs[job_id] = job
        threading.Thread(target=self._run, args=(job_id, payload), daemon=True).start()
        return self.get(job_id)

    def get(self, job_id: str) -> Dict[str, Any]:
        with self._lock:
            if job_id not in self._jobs:
                raise ValueError("Optimization job not found")
            return deepcopy(self._jobs[job_id])

    def cancel(self, job_id: str) -> Dict[str, Any]:
        with self._lock:
            if job_id not in self._jobs:
                raise ValueError("Optimization job not found")
            self._jobs[job_id]["cancel_requested"] = True
            return deepcopy(self._jobs[job_id])

    def _run(self, job_id: str, payload: Dict[str, Any]) -> None:
        db = SessionLocal()
        try:
            self._update(job_id, status="running")
            service = EvaluationService(db)
            result = service.run_optimization_experiments(
                **payload,
                progress_callback=lambda completed, total: self._update(
                    job_id,
                    completed_configurations=completed,
                    total_configurations=total,
                ),
                cancel_check=lambda: self.get(job_id)["cancel_requested"],
            )
            status = "cancelled" if self.get(job_id)["cancel_requested"] else "completed"
            self._update(job_id, status=status, result=result)
        except Exception:
            self._update(
                job_id,
                status="failed",
                error={
                    "code": "optimization_failed",
                    "message": "Optimization failed. Check backend logs for details.",
                },
            )
        finally:
            db.close()

    def _update(self, job_id: str, **values) -> None:
        with self._lock:
            self._jobs[job_id].update(values)


optimization_jobs = OptimizationJobManager()
