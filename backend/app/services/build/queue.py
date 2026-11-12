"""
Centralized Execution Queue Engine
Phase 4 Implementation for Emergent Central Hub

Provides reliable, priority-based execution queue management:
- Priority-based scheduling (CRITICAL > HIGH > MEDIUM > LOW, FIFO tie-breaker)
- Worker registration and heartbeat tracking
- Atomic job claiming to prevent concurrent duplicate execution
- Configurable job execution timeout
- Retry policy with exponential backoff
- Worker crash detection and automated job recovery (Reaper)
- Full state transition auditing in BuildJobHistory
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import case, and_, or_

from app.models.job import BuildJob, BuildJobHistory, BuildWorker
from app.models.account import EmergentAccount
from app.models.project import Project
from app.services.build.state_machine import (
    validate_transition,
    PRIORITY_ORDER,
    InvalidTransitionError,
)
from app.services.build.adapters.base import BaseExecutionAdapter
from app.services.build.adapters.mock_adapter import MockEmergentAdapter
from app.services.build.adapters.real_adapter import RealEmergentAdapter

logger = logging.getLogger("emergent.build.queue")


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class BuildExecutionQueue:
    def __init__(
        self,
        worker_id: str = "worker-default-01",
        heartbeat_timeout_seconds: int = 60,
        default_base_backoff_seconds: int = 5,
    ):
        self.worker_id = worker_id
        self.heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self.base_backoff_seconds = default_base_backoff_seconds
        self.adapters: Dict[str, BaseExecutionAdapter] = {
            "MOCK_EMERGENT": MockEmergentAdapter(),
            "REAL_EMERGENT": RealEmergentAdapter(),
        }

    def get_adapter(self, adapter_name: str) -> BaseExecutionAdapter:
        adapter = self.adapters.get(adapter_name.upper())
        if not adapter:
            logger.warning(f"Unknown adapter '{adapter_name}', falling back to MOCK_EMERGENT")
            return self.adapters["MOCK_EMERGENT"]
        return adapter

    def record_history(
        self,
        db: Session,
        job_id: int,
        from_status: Optional[str],
        to_status: str,
        message: Optional[str] = None,
        error_details: Optional[str] = None,
        worker_id: Optional[str] = None,
    ) -> BuildJobHistory:
        """Records an immutable state transition record in BuildJobHistory."""
        history = BuildJobHistory(
            job_id=job_id,
            from_status=from_status,
            to_status=to_status,
            worker_id=worker_id or self.worker_id,
            message=message,
            error_details=error_details,
            created_at=datetime.now(timezone.utc),
        )
        db.add(history)
        return history

    def register_worker_heartbeat(
        self,
        db: Session,
        worker_name: Optional[str] = None,
        current_job_id: Optional[int] = None,
        system_info: Optional[Dict[str, Any]] = None,
    ) -> BuildWorker:
        """Registers worker presence or updates heartbeat timestamp."""
        w_name = worker_name or self.worker_id
        now = datetime.now(timezone.utc)
        worker = db.query(BuildWorker).filter(BuildWorker.worker_name == w_name).first()
        if not worker:
            worker = BuildWorker(
                worker_name=w_name,
                status="ACTIVE",
                current_job_id=current_job_id,
                system_info=json.dumps(system_info) if system_info else None,
                last_heartbeat_at=now,
            )
            db.add(worker)
        else:
            worker.status = "BUSY" if current_job_id else "ACTIVE"
            worker.current_job_id = current_job_id
            if system_info:
                worker.system_info = json.dumps(system_info)
            worker.last_heartbeat_at = now
            worker.updated_at = now
        db.commit()
        db.refresh(worker)
        return worker

    def claim_next_job(
        self,
        db: Session,
        worker_id: Optional[str] = None,
    ) -> Optional[BuildJob]:
        """
        Atomically claims the highest priority QUEUED job.
        Priority order: CRITICAL (4) > HIGH (3) > MEDIUM (2) > LOW (1), tie-broken by created_at ASC.
        Transitions job from QUEUED -> STARTING.
        """
        w_id = worker_id or self.worker_id
        now = datetime.now(timezone.utc)

        # SQL Case expression for priority weighting
        priority_case = case(
            (BuildJob.priority == "CRITICAL", 4),
            (BuildJob.priority == "HIGH", 3),
            (BuildJob.priority == "MEDIUM", 2),
            (BuildJob.priority == "LOW", 1),
            else_=0,
        )

        # Find next ready job in QUEUED status
        job = (
            db.query(BuildJob)
            .filter(BuildJob.job_status == "QUEUED")
            .order_by(priority_case.desc(), BuildJob.created_at.asc())
            .with_for_update(skip_locked=True)
            .first()
        )

        if not job:
            return None

        # Validate transition QUEUED -> STARTING
        validate_transition(job.job_status, "STARTING", job_id=job.id)

        old_status = job.job_status
        job.job_status = "STARTING"
        job.worker_id = w_id
        job.last_heartbeat_at = now
        job.updated_at = now

        self.record_history(
            db=db,
            job_id=job.id,
            from_status=old_status,
            to_status="STARTING",
            worker_id=w_id,
            message=f"Job claimed by worker {w_id} with priority {job.priority}",
        )
        self.register_worker_heartbeat(db, worker_name=w_id, current_job_id=job.id)

        db.commit()
        db.refresh(job)
        logger.info(f"Worker {w_id} successfully claimed job #{job.id} (priority: {job.priority})")
        return job

    def execute_claimed_job(
        self,
        db: Session,
        job_id: int,
        worker_id: Optional[str] = None,
    ) -> BuildJob:
        """
        Executes the job through its configured execution adapter.
        Transitions: STARTING -> RUNNING -> COMPLETED (or FAILED with retry).
        """
        w_id = worker_id or self.worker_id
        now = datetime.now(timezone.utc)

        job = db.query(BuildJob).filter(BuildJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job #{job_id} not found")

        project = db.query(Project).filter(Project.id == job.project_id).first()
        account = db.query(EmergentAccount).filter(EmergentAccount.id == job.account_id).first()
        if not project or not account:
            job.job_status = "FAILED"
            job.error_details = "Associated Project or Emergent Account missing"
            job.completed_at = now
            db.commit()
            return job

        adapter = self.get_adapter(job.execution_adapter)

        # Transition STARTING -> RUNNING
        validate_transition(job.job_status, "RUNNING", job_id=job.id)
        old_status = job.job_status
        job.job_status = "RUNNING"
        job.started_at = job.started_at or now
        job.last_heartbeat_at = now
        self.record_history(
            db=db,
            job_id=job.id,
            from_status=old_status,
            to_status="RUNNING",
            worker_id=w_id,
            message=f"Execution started using adapter {adapter.adapter_name}",
        )
        db.commit()

        # Execute through adapter
        try:
            prepared = adapter.prepare_execution_request(job, project, account)
            submission = adapter.submit_build(job, account, prepared)
            
            # Update heartbeat before polling
            job.last_heartbeat_at = datetime.now(timezone.utc)
            db.commit()

            poll_result = adapter.poll_execution_status(job, account)

            # Never mark COMPLETED unless the execution adapter confirms successful completion!
            if poll_result.get("status") == "COMPLETED":
                validate_transition(job.job_status, "COMPLETED", job_id=job.id)
                job.job_status = "COMPLETED"
                job.completed_at = datetime.now(timezone.utc)
                job.credits_used = poll_result.get("credits_used", job.credits_used)
                job.result_summary = poll_result.get("result_summary")
                job.result_metadata = poll_result.get("result_metadata")
                job.error_details = None
                job.worker_id = None

                self.record_history(
                    db=db,
                    job_id=job.id,
                    from_status="RUNNING",
                    to_status="COMPLETED",
                    worker_id=w_id,
                    message="Build completed successfully confirmed by adapter",
                )
                self.register_worker_heartbeat(db, worker_name=w_id, current_job_id=None)

                # Record CreditEvent and synchronize budget
                try:
                    from decimal import Decimal
                    from app.models.credit import CreditEvent
                    from app.models.autonomous import AccountCreditBudget

                    budget = db.query(AccountCreditBudget).filter(AccountCreditBudget.account_id == job.account_id).first()
                    used_amt = Decimal(str(job.credits_used or "0.7500"))
                    if budget:
                        budget.credit_usage += used_amt
                        budget.platform_build_usage += used_amt
                        budget.verified_current_balance = max(Decimal("0.0000"), budget.verified_current_balance - used_amt)

                    evt = CreditEvent(
                        account_id=job.account_id,
                        event_type="consume",
                        amount=used_amt,
                        balance_after=budget.verified_current_balance if budget else None,
                        job_id=job.id,
                        notes=f"Build #{job.id} execution: {job.title}",
                        event_timestamp=datetime.now(timezone.utc),
                    )
                    db.add(evt)
                except Exception as credit_err:
                    logger.warning(f"Note on credit deduction for build #{job.id}: {credit_err}")

                db.commit()
                db.refresh(job)
                logger.info(f"Job #{job.id} marked COMPLETED by adapter {adapter.adapter_name}")
                return job
            else:
                raise RuntimeError(poll_result.get("error") or "Adapter execution did not confirm completion")

        except Exception as e:
            err_msg = str(e)
            logger.error(f"Error executing job #{job.id}: {err_msg}", exc_info=True)
            return self.handle_job_failure(db=db, job=job, error_message=err_msg, worker_id=w_id)

    def handle_job_failure(
        self,
        db: Session,
        job: BuildJob,
        error_message: str,
        worker_id: Optional[str] = None,
    ) -> BuildJob:
        """
        Handles job failure applying retry policy with exponential backoff.
        If retry_count < max_retries: re-queues to QUEUED.
        If retry limit reached: marks FAILED.
        """
        w_id = worker_id or self.worker_id
        now = datetime.now(timezone.utc)

        if job.retry_count < job.max_retries:
            job.retry_count += 1
            backoff_delay = self.base_backoff_seconds * (2 ** (job.retry_count - 1))
            
            # Transition FAILED -> QUEUED (or directly back to QUEUED)
            old_status = job.job_status
            job.job_status = "QUEUED"
            job.error_details = f"Attempt {job.retry_count}/{job.max_retries} failed: {error_message}"
            job.worker_id = None
            job.last_heartbeat_at = None

            self.record_history(
                db=db,
                job_id=job.id,
                from_status=old_status,
                to_status="QUEUED",
                worker_id=w_id,
                message=f"Scheduled retry {job.retry_count}/{job.max_retries} with {backoff_delay}s exponential backoff",
                error_details=error_message,
            )
            self.register_worker_heartbeat(db, worker_name=w_id, current_job_id=None)
            db.commit()
            db.refresh(job)
            logger.warning(f"Job #{job.id} re-queued for retry {job.retry_count}/{job.max_retries}")
            return job
        else:
            old_status = job.job_status
            job.job_status = "FAILED"
            job.completed_at = now
            job.error_details = f"Exhausted all {job.max_retries} retries. Final error: {error_message}"
            job.worker_id = None

            self.record_history(
                db=db,
                job_id=job.id,
                from_status=old_status,
                to_status="FAILED",
                worker_id=w_id,
                message=f"Job marked FAILED after exhausting {job.max_retries} retries",
                error_details=error_message,
            )
            self.register_worker_heartbeat(db, worker_name=w_id, current_job_id=None)
            db.commit()
            db.refresh(job)
            logger.critical(f"Job #{job.id} marked FAILED after exhausting max retries")
            return job

    def cancel_job(
        self,
        db: Session,
        job_id: int,
        user_id: int,
        reason: Optional[str] = None,
    ) -> BuildJob:
        """Cancels a job if it is not in a terminal state."""
        job = db.query(BuildJob).filter(BuildJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job #{job_id} not found")

        validate_transition(job.job_status, "CANCELLED", job_id=job.id)

        old_status = job.job_status
        now = datetime.now(timezone.utc)
        job.job_status = "CANCELLED"
        job.cancelled_at = now
        job.completed_at = now
        job.worker_id = None

        msg = f"Job cancelled by user #{user_id}."
        if reason:
            msg += f" Reason: {reason}"

        self.record_history(
            db=db,
            job_id=job.id,
            from_status=old_status,
            to_status="CANCELLED",
            message=msg,
        )
        db.commit()
        db.refresh(job)
        return job

    def pause_job(self, db: Session, job_id: int, user_id: int) -> BuildJob:
        """Pauses an actively RUNNING job."""
        job = db.query(BuildJob).filter(BuildJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job #{job_id} not found")

        validate_transition(job.job_status, "PAUSED", job_id=job.id)
        old_status = job.job_status
        now = datetime.now(timezone.utc)
        job.job_status = "PAUSED"
        job.paused_at = now

        self.record_history(
            db=db,
            job_id=job.id,
            from_status=old_status,
            to_status="PAUSED",
            message=f"Job paused by user #{user_id}",
        )
        db.commit()
        db.refresh(job)
        return job

    def resume_job(self, db: Session, job_id: int, user_id: int) -> BuildJob:
        """Resumes a PAUSED job back to RUNNING."""
        job = db.query(BuildJob).filter(BuildJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job #{job_id} not found")

        validate_transition(job.job_status, "RUNNING", job_id=job.id)
        old_status = job.job_status
        job.job_status = "RUNNING"
        job.last_heartbeat_at = datetime.now(timezone.utc)

        self.record_history(
            db=db,
            job_id=job.id,
            from_status=old_status,
            to_status="RUNNING",
            message=f"Job resumed by user #{user_id}",
        )
        db.commit()
        db.refresh(job)
        return job

    def retry_job(self, db: Session, job_id: int, user_id: int) -> BuildJob:
        """Re-enqueues a FAILED job."""
        job = db.query(BuildJob).filter(BuildJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job #{job_id} not found")

        validate_transition(job.job_status, "QUEUED", job_id=job.id)
        old_status = job.job_status
        job.job_status = "QUEUED"
        job.error_details = None
        job.completed_at = None
        job.worker_id = None
        job.last_heartbeat_at = None

        self.record_history(
            db=db,
            job_id=job.id,
            from_status=old_status,
            to_status="QUEUED",
            message=f"Job manually retried by user #{user_id}",
        )
        db.commit()
        db.refresh(job)
        return job

    def check_timeouts_and_reap_crashes(
        self,
        db: Session,
        stale_threshold_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        WORKER CRASH RECOVERY & TIMEOUT REAPER:
        1. Identifies RUNNING or STARTING jobs where worker heartbeat is missing or older
           than stale_threshold_seconds (worker crash).
        2. Recovers crashed jobs by applying retry policy (re-queuing if retries remain).
        3. Identifies jobs that exceeded timeout_seconds and marks them FAILED.
        """
        threshold = stale_threshold_seconds or self.heartbeat_timeout_seconds
        now = datetime.now(timezone.utc)
        cutoff_heartbeat = now - timedelta(seconds=threshold)

        recovered_count = 0
        timed_out_count = 0

        # Query active jobs in STARTING or RUNNING
        active_jobs = (
            db.query(BuildJob)
            .filter(BuildJob.job_status.in_(["STARTING", "RUNNING"]))
            .all()
        )

        for job in active_jobs:
            job_started_at = ensure_utc(job.started_at)
            job_last_heartbeat = ensure_utc(job.last_heartbeat_at)

            # 1. Check job execution timeout
            if job_started_at:
                elapsed_seconds = (now - job_started_at).total_seconds()
                if elapsed_seconds > job.timeout_seconds:
                    logger.warning(f"Job #{job.id} exceeded timeout of {job.timeout_seconds}s (elapsed: {int(elapsed_seconds)}s)")
                    old_status = job.job_status
                    job.job_status = "FAILED"
                    job.completed_at = now
                    job.error_details = f"Execution timed out after {int(elapsed_seconds)}s (limit: {job.timeout_seconds}s)"
                    job.worker_id = None

                    self.record_history(
                        db=db,
                        job_id=job.id,
                        from_status=old_status,
                        to_status="FAILED",
                        message="Job terminated due to timeout limit exceeded",
                        error_details=job.error_details,
                    )
                    timed_out_count += 1
                    continue

            # 2. Check worker heartbeat staleness (worker crash detection)
            is_stale_heartbeat = False
            if job_last_heartbeat:
                if job_last_heartbeat < cutoff_heartbeat:
                    is_stale_heartbeat = True
            elif job_started_at and job_started_at < cutoff_heartbeat:
                is_stale_heartbeat = True

            if is_stale_heartbeat:
                crashed_worker = job.worker_id or "unknown"
                logger.critical(
                    f"Worker crash detected for job #{job.id}: Worker '{crashed_worker}' has no heartbeat for >{threshold}s"
                )
                self.handle_job_failure(
                    db=db,
                    job=job,
                    error_message=f"Worker crash detected: Worker '{crashed_worker}' heartbeat lost for >{threshold}s",
                )
                recovered_count += 1

        db.commit()
        return {
            "recovered_crashed_jobs": recovered_count,
            "timed_out_jobs": timed_out_count,
            "timestamp": now.isoformat(),
        }
