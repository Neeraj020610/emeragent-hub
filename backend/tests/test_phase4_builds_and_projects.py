"""
Phase 4 Tests — Build Manager, Project Management, and Centralized Execution Engine
Emergent Central Hub
"""
import json
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi import status

from app.models.account import EmergentAccount, AccountPermission, PersonalAccountConsent
from app.models.project import Project, ProjectMember
from app.models.job import BuildJob, JobAssignment, BuildJobHistory, BuildWorker
from app.models.user import User
from app.models.audit import AuditLog
from app.services.build.state_machine import validate_transition, InvalidTransitionError
from app.services.build.queue import BuildExecutionQueue
from app.services.build.service import BuildService


# -------------------------------------------------------------
# 1. Project Creation, Editing, and Member Access
# -------------------------------------------------------------
def test_project_creation_and_listing(client, admin_token, manager_token, db_session):
    manager_user = db_session.query(User).filter(User.email == "manager@emergent-hub.com").first()
    acc = EmergentAccount(
        account_identifier="EMG-PROJ-TEST-01",
        account_name="Project Test Account",
        email="proj-test@company.internal",
        ownership_type="COMPANY_OWNED",
        status="active",
    )
    db_session.add(acc)
    db_session.commit()

    # Admin creates project and assigns manager
    resp = client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "account_id": acc.id,
            "project_name": "Autonomous Agent V1",
            "project_key": "AGENT-V1",
            "description": "Next-gen agent runtime",
            "status": "PLANNING",
            "member_user_ids": [manager_user.id],
        },
    )
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["project_key"] == "AGENT-V1"
    assert data["status"] == "PLANNING"
    proj_id = data["id"]

    # Verify duplicate project_key rejection
    dupe_resp = client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "account_id": acc.id,
            "project_name": "Another Agent",
            "project_key": "AGENT-V1",
        },
    )
    assert dupe_resp.status_code == status.HTTP_409_CONFLICT

    # Manager updates project
    upd_resp = client.put(
        f"/api/v1/projects/{proj_id}",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={
            "project_name": "Autonomous Agent V1 (Active)",
            "status": "ACTIVE",
            "tags": "ai,llm,agents",
        },
    )
    assert upd_resp.status_code == status.HTTP_200_OK
    assert upd_resp.json()["status"] == "ACTIVE"
    assert upd_resp.json()["tags"] == "ai,llm,agents"


def test_project_access_and_member_assignment(client, admin_token, member_token, db_session):
    member_user = db_session.query(User).filter(User.email == "member@emergent-hub.com").first()
    acc = EmergentAccount(
        account_identifier="EMG-PROJ-TEST-02",
        account_name="Isolation Test Account",
        email="iso-test@company.internal",
        ownership_type="COMPANY_OWNED",
        status="active",
    )
    db_session.add(acc)
    db_session.commit()

    # Admin creates project
    proj = Project(
        account_id=acc.id,
        project_name="Isolated Core System",
        project_key="ISO-CORE",
        status="ACTIVE",
    )
    db_session.add(proj)
    db_session.commit()

    # Member attempts to get project details before being assigned -> 403
    resp_unassigned = client.get(
        f"/api/v1/projects/{proj.id}",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert resp_unassigned.status_code == status.HTTP_403_FORBIDDEN

    # Admin assigns member to project
    assign_resp = client.post(
        f"/api/v1/projects/{proj.id}/members",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "user_id": member_user.id,
            "role_in_project": "developer",
        },
    )
    assert assign_resp.status_code == status.HTTP_200_OK
    assert assign_resp.json()["user_id"] == member_user.id
    assert assign_resp.json()["role_in_project"] == "developer"

    # Member can now access project details
    resp_assigned = client.get(
        f"/api/v1/projects/{proj.id}",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert resp_assigned.status_code == status.HTTP_200_OK
    assert resp_assigned.json()["project_key"] == "ISO-CORE"

    # Member cannot edit project (Manager/Admin required) -> 403
    edit_resp = client.put(
        f"/api/v1/projects/{proj.id}",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"project_name": "Hacked Name"},
    )
    assert edit_resp.status_code == status.HTTP_403_FORBIDDEN

    # Admin removes member from project
    del_resp = client.delete(
        f"/api/v1/projects/{proj.id}/members/{member_user.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert del_resp.status_code == status.HTTP_204_NO_CONTENT

    # Access is revoked
    resp_revoked = client.get(
        f"/api/v1/projects/{proj.id}",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert resp_revoked.status_code == status.HTTP_403_FORBIDDEN


# -------------------------------------------------------------
# 2. Build Job Creation, Idempotency, and Account Permission Gates
# -------------------------------------------------------------
def test_build_creation_and_idempotency(client, admin_token, db_session):
    acc = EmergentAccount(
        account_identifier="EMG-BUILD-TEST-01",
        account_name="Build Hub Account",
        email="build-hub@company.internal",
        ownership_type="COMPANY_OWNED",
        status="active",
    )
    db_session.add(acc)
    db_session.commit()

    proj = Project(
        account_id=acc.id,
        project_name="Build Automation System",
        project_key="BUILD-AUTO",
        status="ACTIVE",
    )
    db_session.add(proj)
    db_session.commit()

    # Create build with full requirements, references, priority, and idempotency key
    idem_key = "idem_build_req_999111"
    create_payload = {
        "project_id": proj.id,
        "account_id": acc.id,
        "title": "Compile Full Stack Kernel",
        "job_type": "full_stack",
        "priority": "HIGH",
        "requirements": "Generate FastAPI endpoints, React frontend views, and migration scripts.",
        "reference_urls": ["https://docs.emergent.ai/architecture", "https://github.com/company/repo"],
        "notes": "Ensure high-performance indexing on SQLite.",
        "auto_start": True,
        "idempotency_key": idem_key,
    }

    resp = client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=create_payload,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["title"] == "Compile Full Stack Kernel"
    assert data["job_status"] == "QUEUED"  # auto_start=True
    assert data["priority"] == "HIGH"
    assert data["idempotency_key"] == idem_key
    assert len(data["reference_urls"]) == 2
    assert len(data["assignments"]) == 1
    job_id = data["id"]

    # Duplicate submission with SAME idempotency key -> 409 Conflict
    dupe_resp = client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=create_payload,
    )
    assert dupe_resp.status_code == status.HTTP_409_CONFLICT
    assert "duplicate build submission" in dupe_resp.json()["detail"].lower()

    # Verify audit log was recorded
    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.resource_type == "build_job", AuditLog.resource_id == str(job_id))
        .first()
    )
    assert audit is not None
    assert "Compile Full Stack Kernel" in audit.details


def test_account_permission_and_consent_enforcement_on_builds(client, admin_token, member_token, db_session):
    admin_user = db_session.query(User).filter(User.email == "admin@emergent-hub.com").first()
    member_user = db_session.query(User).filter(User.email == "member@emergent-hub.com").first()

    # 1. Company account with restrictive permission (can_execute=False)
    acc_no_perm = EmergentAccount(
        account_identifier="EMG-NO-PERM-01",
        account_name="Restricted Account",
        email="restricted@company.internal",
        ownership_type="COMPANY_OWNED",
        status="active",
    )
    db_session.add(acc_no_perm)
    db_session.commit()

    perm_restrictive = AccountPermission(
        user_id=member_user.id,
        account_id=acc_no_perm.id,
        can_view=True,
        can_execute=False,
    )
    db_session.add(perm_restrictive)
    db_session.commit()

    proj1 = Project(
        account_id=acc_no_perm.id,
        project_name="Restricted Project",
        project_key="RESTRICTED-P",
        status="ACTIVE",
    )
    db_session.add(proj1)
    db_session.commit()

    # Assign member to project
    pm1 = ProjectMember(project_id=proj1.id, user_id=member_user.id)
    db_session.add(pm1)
    db_session.commit()

    # Member attempts build -> 403 Forbidden (can_execute=False on account)
    resp_no_perm = client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "project_id": proj1.id,
            "account_id": acc_no_perm.id,
            "title": "Unauthorized Build",
            "job_type": "prompt_build",
        },
    )
    assert resp_no_perm.status_code == status.HTTP_403_FORBIDDEN
    assert "can_execute" in resp_no_perm.json()["detail"].lower()

    # Grant can_execute permission
    perm_restrictive.can_execute = True
    db_session.commit()

    # Member build now succeeds
    resp_perm_ok = client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "project_id": proj1.id,
            "account_id": acc_no_perm.id,
            "title": "Authorized Company Build",
            "job_type": "prompt_build",
        },
    )
    assert resp_perm_ok.status_code == status.HTTP_201_CREATED

    # 2. Personal account owned by Admin
    personal_acc = EmergentAccount(
        account_identifier="EMG-PERS-TEST-01",
        account_name="Admin Personal Account",
        email="admin-personal@company.internal",
        owner_user_id=admin_user.id,
        ownership_type="PERSONAL",
        status="active",
    )
    db_session.add(personal_acc)
    db_session.commit()

    proj2 = Project(
        account_id=personal_acc.id,
        project_name="Personal Project",
        project_key="PERS-P",
        status="ACTIVE",
    )
    db_session.add(proj2)
    db_session.commit()

    pm2 = ProjectMember(project_id=proj2.id, user_id=member_user.id)
    db_session.add(pm2)
    db_session.commit()

    # Member attempts build on personal account -> 403 Forbidden (no consent)
    resp_no_consent = client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "project_id": proj2.id,
            "account_id": personal_acc.id,
            "title": "Attempt on Personal Account",
            "job_type": "prompt_build",
        },
    )
    assert resp_no_consent.status_code == status.HTTP_403_FORBIDDEN
    assert "owner consent is required" in resp_no_consent.json()["detail"].lower()

    # Grant active server-side PersonalAccountConsent
    consent = PersonalAccountConsent(
        account_id=personal_acc.id,
        owner_user_id=admin_user.id,
        authorized_member_id=member_user.id,
        permission_scope="BUILD_EXECUTION",
        is_active=True,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db_session.add(consent)
    db_session.commit()

    # Now member build succeeds
    resp_consent_ok = client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "project_id": proj2.id,
            "account_id": personal_acc.id,
            "title": "Consent Authorized Build",
            "job_type": "prompt_build",
        },
    )
    assert resp_consent_ok.status_code == status.HTTP_201_CREATED


# -------------------------------------------------------------
# 3. Status Transition State Machine Rules
# -------------------------------------------------------------
def test_valid_and_invalid_status_transitions():
    # Valid transitions
    assert validate_transition("DRAFT", "QUEUED") is None
    assert validate_transition("QUEUED", "STARTING") is None
    assert validate_transition("STARTING", "RUNNING") is None
    assert validate_transition("RUNNING", "PAUSED") is None
    assert validate_transition("PAUSED", "RUNNING") is None
    assert validate_transition("RUNNING", "COMPLETED") is None
    assert validate_transition("FAILED", "QUEUED") is None  # Retry

    # Invalid transitions must raise InvalidTransitionError
    with pytest.raises(InvalidTransitionError):
        validate_transition("DRAFT", "COMPLETED")

    with pytest.raises(InvalidTransitionError):
        validate_transition("COMPLETED", "RUNNING")

    with pytest.raises(InvalidTransitionError):
        validate_transition("CANCELLED", "QUEUED")

    with pytest.raises(InvalidTransitionError):
        validate_transition("PAUSED", "COMPLETED")


def test_api_status_transition_endpoints(client, admin_token, db_session):
    acc = EmergentAccount(
        account_identifier="EMG-STATE-01",
        account_name="State Machine Account",
        email="state@company.internal",
        ownership_type="COMPANY_OWNED",
        status="active",
    )
    db_session.add(acc)
    db_session.commit()

    proj = Project(
        account_id=acc.id,
        project_name="State Workflow",
        project_key="STATE-WF",
        status="ACTIVE",
    )
    db_session.add(proj)
    db_session.commit()

    # Create job in DRAFT (auto_start=False)
    create_resp = client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "project_id": proj.id,
            "account_id": acc.id,
            "title": "State Flow Job",
            "job_type": "prompt_build",
            "auto_start": False,
        },
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    job_id = create_resp.json()["id"]
    assert create_resp.json()["job_status"] == "DRAFT"

    # Start job -> QUEUED
    start_resp = client.post(
        f"/api/v1/jobs/{job_id}/start",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert start_resp.status_code == status.HTTP_200_OK
    assert start_resp.json()["job_status"] == "QUEUED"

    # Attempt illegal pause on QUEUED job -> 400 Bad Request
    illegal_pause = client.post(
        f"/api/v1/jobs/{job_id}/pause",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert illegal_pause.status_code == status.HTTP_400_BAD_REQUEST
    assert "cannot transition" in illegal_pause.json()["detail"].lower()

    # Cancel job -> CANCELLED
    cancel_resp = client.post(
        f"/api/v1/jobs/{job_id}/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"reason": "User changed mind"},
    )
    assert cancel_resp.status_code == status.HTTP_200_OK
    assert cancel_resp.json()["job_status"] == "CANCELLED"
    assert cancel_resp.json()["cancelled_at"] is not None


# -------------------------------------------------------------
# 4. Priority-Based Scheduling & Execution Queue Engine
# -------------------------------------------------------------
def test_priority_scheduling_order(db_session):
    queue = BuildExecutionQueue()

    acc = EmergentAccount(
        account_identifier="EMG-QUEUE-ORDER-01",
        account_name="Priority Account",
        email="priority@company.internal",
        ownership_type="COMPANY_OWNED",
        status="active",
    )
    db_session.add(acc)
    db_session.commit()

    proj = Project(
        account_id=acc.id,
        project_name="Priority Project",
        project_key="PRIO-PROJ",
        status="ACTIVE",
    )
    db_session.add(proj)
    db_session.commit()

    # Enqueue jobs in order: LOW, MEDIUM, CRITICAL, HIGH
    j_low = BuildJob(project_id=proj.id, account_id=acc.id, title="Low Job", job_type="test", job_status="QUEUED", priority="LOW")
    j_med = BuildJob(project_id=proj.id, account_id=acc.id, title="Medium Job", job_type="test", job_status="QUEUED", priority="MEDIUM")
    j_crit = BuildJob(project_id=proj.id, account_id=acc.id, title="Critical Job", job_type="test", job_status="QUEUED", priority="CRITICAL")
    j_high = BuildJob(project_id=proj.id, account_id=acc.id, title="High Job", job_type="test", job_status="QUEUED", priority="HIGH")

    db_session.add_all([j_low, j_med, j_crit, j_high])
    db_session.commit()

    # Claims must be strictly: CRITICAL -> HIGH -> MEDIUM -> LOW
    c1 = queue.claim_next_job(db=db_session)
    assert c1.id == j_crit.id
    assert c1.priority == "CRITICAL"
    assert c1.job_status == "STARTING"

    c2 = queue.claim_next_job(db=db_session)
    assert c2.id == j_high.id
    assert c2.priority == "HIGH"

    c3 = queue.claim_next_job(db=db_session)
    assert c3.id == j_med.id
    assert c3.priority == "MEDIUM"

    c4 = queue.claim_next_job(db=db_session)
    assert c4.id == j_low.id
    assert c4.priority == "LOW"

    # Queue is now empty
    assert queue.claim_next_job(db=db_session) is None


# -------------------------------------------------------------
# 5. Retry Policy, Worker Crash Recovery & Timeout Reaper
# -------------------------------------------------------------
def test_retry_policy_with_exponential_backoff(db_session):
    queue = BuildExecutionQueue(default_base_backoff_seconds=2)

    acc = EmergentAccount(
        account_identifier="EMG-RETRY-01",
        account_name="Retry Account",
        email="retry@company.internal",
        ownership_type="COMPANY_OWNED",
        status="active",
    )
    db_session.add(acc)
    db_session.commit()

    proj = Project(
        account_id=acc.id,
        project_name="Retry Project",
        project_key="RETRY-P",
        status="ACTIVE",
    )
    db_session.add(proj)
    db_session.commit()

    job = BuildJob(
        project_id=proj.id,
        account_id=acc.id,
        title="Flaky Job",
        job_type="test",
        job_status="RUNNING",
        priority="HIGH",
        retry_count=0,
        max_retries=2,
    )
    db_session.add(job)
    db_session.commit()

    # Failure 1 -> Retry 1 (re-queued)
    queue.handle_job_failure(db=db_session, job=job, error_message="Network glitch 1")
    assert job.job_status == "QUEUED"
    assert job.retry_count == 1
    assert "Attempt 1/2 failed" in job.error_details

    # Failure 2 -> Retry 2 (re-queued)
    queue.handle_job_failure(db=db_session, job=job, error_message="Network glitch 2")
    assert job.job_status == "QUEUED"
    assert job.retry_count == 2
    assert "Attempt 2/2 failed" in job.error_details

    # Failure 3 -> Max retries reached -> FAILED
    queue.handle_job_failure(db=db_session, job=job, error_message="Permanent provider error")
    assert job.job_status == "FAILED"
    assert "exhausted all 2 retries" in job.error_details.lower()
    assert job.completed_at is not None


def test_worker_crash_recovery_reaper(db_session):
    """
    Simulates a worker crashing while a job is RUNNING.
    The reaper detects stale heartbeat (>60s) and automatically re-queues the job.
    """
    queue = BuildExecutionQueue(heartbeat_timeout_seconds=30)

    acc = EmergentAccount(
        account_identifier="EMG-CRASH-01",
        account_name="Crash Recovery Account",
        email="crash@company.internal",
        ownership_type="COMPANY_OWNED",
        status="active",
    )
    db_session.add(acc)
    db_session.commit()

    proj = Project(
        account_id=acc.id,
        project_name="Crash Project",
        project_key="CRASH-P",
        status="ACTIVE",
    )
    db_session.add(proj)
    db_session.commit()

    # Job running with stale heartbeat 90s ago
    past_heartbeat = datetime.now(timezone.utc) - timedelta(seconds=90)
    job = BuildJob(
        project_id=proj.id,
        account_id=acc.id,
        title="Crashed Worker Job",
        job_type="test",
        job_status="RUNNING",
        priority="HIGH",
        worker_id="crashed-worker-77",
        last_heartbeat_at=past_heartbeat,
        started_at=past_heartbeat,
        retry_count=0,
        max_retries=3,
    )
    db_session.add(job)
    db_session.commit()

    # Run reaper sweep
    reap_result = queue.check_timeouts_and_reap_crashes(db=db_session, stale_threshold_seconds=30)
    assert reap_result["recovered_crashed_jobs"] == 1

    # Job is recovered back to QUEUED status with retry_count=1
    db_session.refresh(job)
    assert job.job_status == "QUEUED"
    assert job.retry_count == 1
    assert "worker crash detected" in job.error_details.lower()


def test_job_execution_timeout(db_session):
    """
    Verifies that a job running beyond timeout_seconds is terminated as FAILED.
    """
    queue = BuildExecutionQueue()

    acc = EmergentAccount(
        account_identifier="EMG-TIMEOUT-01",
        account_name="Timeout Account",
        email="timeout@company.internal",
        ownership_type="COMPANY_OWNED",
        status="active",
    )
    db_session.add(acc)
    db_session.commit()

    proj = Project(
        account_id=acc.id,
        project_name="Timeout Project",
        project_key="TIME-P",
        status="ACTIVE",
    )
    db_session.add(proj)
    db_session.commit()

    # Started 120s ago with timeout of 60s
    past_time = datetime.now(timezone.utc) - timedelta(seconds=120)
    job = BuildJob(
        project_id=proj.id,
        account_id=acc.id,
        title="Hanging Job",
        job_type="test",
        job_status="RUNNING",
        timeout_seconds=60,
        started_at=past_time,
        last_heartbeat_at=datetime.now(timezone.utc),  # Heartbeat is fine, but elapsed time exceeded!
    )
    db_session.add(job)
    db_session.commit()

    reap_result = queue.check_timeouts_and_reap_crashes(db=db_session)
    assert reap_result["timed_out_jobs"] == 1

    db_session.refresh(job)
    assert job.job_status == "FAILED"
    assert "timed out" in job.error_details.lower()


# -------------------------------------------------------------
# 6. Mock Adapter Execution, Disclaimers, and Dashboard Stats
# -------------------------------------------------------------
def test_mock_adapter_execution_flow(client, admin_token, db_session):
    acc = EmergentAccount(
        account_identifier="EMG-MOCK-EXEC-01",
        account_name="Mock Exec Account",
        email="mock-exec@company.internal",
        ownership_type="COMPANY_OWNED",
        status="active",
    )
    db_session.add(acc)
    db_session.commit()

    proj = Project(
        account_id=acc.id,
        project_name="Mock Exec Project",
        project_key="MOCK-EXEC",
        status="ACTIVE",
    )
    db_session.add(proj)
    db_session.commit()

    # Create job in QUEUED status
    create_resp = client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "project_id": proj.id,
            "account_id": acc.id,
            "title": "Complete Build Simulation",
            "job_type": "full_stack",
            "priority": "HIGH",
            "auto_start": True,
        },
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    job_id = create_resp.json()["id"]

    # Trigger queue processor
    proc_resp = client.post(
        "/api/v1/jobs/queue/process-next",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert proc_resp.status_code == status.HTTP_200_OK
    exec_data = proc_resp.json()
    assert exec_data["id"] == job_id
    assert exec_data["job_status"] == "COMPLETED"
    assert exec_data["is_mock"] is True
    assert exec_data["execution_adapter"] == "MOCK_EMERGENT"
    assert float(exec_data["credits_used"]) > 0

    # Verify result metadata contains mock disclaimer
    assert "mock" in exec_data["result_metadata"].lower()
    assert "disclaimer" in exec_data["result_metadata"].lower()

    # Query detailed build
    det_resp = client.get(
        f"/api/v1/jobs/{job_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert det_resp.status_code == status.HTTP_200_OK
    assert len(det_resp.json()["history"]) >= 3  # QUEUED -> STARTING -> RUNNING -> COMPLETED

    # Check dashboard stats
    stats_resp = client.get(
        "/api/v1/jobs/dashboard/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert stats_resp.status_code == status.HTTP_200_OK
    stats = stats_resp.json()
    assert stats["total_builds"] >= 1
    assert stats["completed_builds"] >= 1
    assert stats["mock_execution_count"] >= 1
    assert stats["real_execution_count"] == 0
    assert stats["execution_enabled"] is False
