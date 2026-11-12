import json
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.models.user import User, Role
from app.models.account import EmergentAccount
from app.models.session import AccountSession
from app.models.autonomous import (
    AutonomousInstruction,
    AutonomousTask,
    AccountCreditBudget,
    AutonomousSystemState,
)
from app.services.autonomous.brain import AutonomousBrainService
from app.services.autonomous.scheduler import AccountCreditScheduler
from app.services.autonomous.worker_engine import AutonomousWorkerEngine
from app.services.autonomous.control import AutonomousControlService


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def autonomous_accounts(db_session):
    """Sets up two active test Emergent accounts with valid active sessions and starting balances."""
    admin_user = db_session.query(User).filter(User.email == settings.INITIAL_ADMIN_EMAIL).first()

    acc_a = EmergentAccount(
        account_identifier="ACC-AUTO-001",
        account_name="Autonomous Production Account A",
        email="auto-a@emergent.sh",
        ownership_type="COMPANY_OWNED",
        owner_user_id=admin_user.id if admin_user else None,
        status="active",
        connection_status="CONNECTED",
    )
    acc_b = EmergentAccount(
        account_identifier="ACC-AUTO-002",
        account_name="Autonomous Production Account B",
        email="auto-b@emergent.sh",
        ownership_type="COMPANY_OWNED",
        owner_user_id=admin_user.id if admin_user else None,
        status="active",
        connection_status="CONNECTED",
    )
    db_session.add_all([acc_a, acc_b])
    db_session.commit()
    db_session.refresh(acc_a)
    db_session.refresh(acc_b)

    # Active sessions
    sess_a = AccountSession(
        account_id=acc_a.id,
        session_token="sess-token-auto-a",
        auth_method="browser_profile",
        session_status="ACTIVE",
    )
    sess_b = AccountSession(
        account_id=acc_b.id,
        session_token="sess-token-auto-b",
        auth_method="browser_profile",
        session_status="ACTIVE",
    )
    db_session.add_all([sess_a, sess_b])
    db_session.commit()

    # Budgets: $100 starting balance, 50% ceiling ($50)
    scheduler = AccountCreditScheduler()
    budget_a = scheduler.update_account_budget(
        account_id=acc_a.id,
        starting_balance=Decimal("100.0000"),
        ceiling_percentage=Decimal("50.00"),
        balance_source="API_VERIFIED",
        db=db_session,
    )
    budget_b = scheduler.update_account_budget(
        account_id=acc_b.id,
        starting_balance=Decimal("100.0000"),
        ceiling_percentage=Decimal("50.00"),
        balance_source="API_VERIFIED",
        db=db_session,
    )

    return acc_a, acc_b


def test_create_instruction_and_generate_bounded_plan(client: TestClient, admin_headers: dict, db_session):
    """
    Phase 5A: Creates an administrator reusable instruction and verifies the Autonomous Brain
    generates bounded actionable tasks with acceptance criteria.
    """
    payload = {
        "title": "Autonomous Product Demo Video Pipeline",
        "work_type": "VIDEO_CREATION",
        "objective": "Produce a 20-second high-conversion product demonstration video.",
        "max_tasks": 5,
        "parameters": {"duration": 20, "resolution": "1920x1080", "format": "mp4"},
    }
    res = client.post("/api/v1/autonomous/instructions", json=payload, headers=admin_headers)
    assert res.status_code == 200, res.text
    inst_data = res.json()
    assert inst_data["id"] is not None
    assert inst_data["work_type"] == "VIDEO_CREATION"
    inst_id = inst_data["id"]

    # Generate plan and tasks
    plan_res = client.post(f"/api/v1/autonomous/instructions/{inst_id}/plan", headers=admin_headers)
    assert plan_res.status_code == 200, plan_res.text
    tasks = plan_res.json()
    assert len(tasks) >= 3
    for t in tasks:
        assert t["work_type"] == "VIDEO_CREATION"
        assert t["acceptance_criteria"] is not None
        assert t["status"] == "PLANNED"
        assert t["priority"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    # Calling plan generation again must not create duplicates or exceed max_tasks
    plan_res_2 = client.post(f"/api/v1/autonomous/instructions/{inst_id}/plan", headers=admin_headers)
    assert plan_res_2.status_code == 200
    assert len(plan_res_2.json()) == len(tasks)


def test_manual_task_creation_and_bulk_import(client: TestClient, admin_headers: dict):
    """
    Phase 5A: Verifies creation of manual tasks and bulk-imported task lists.
    """
    # Manual task
    manual_payload = {
        "title": "Fix React Memory Leak in Dashboard",
        "work_type": "WEBSITE_APP_DEV",
        "source": "MANUAL",
        "description": "Investigate and resolve unmounted listener leak in Overview charts.",
        "expected_result": "Zero memory leaks verified on profiler test.",
        "acceptance_criteria": ["Profiler memory stable after 50 route navigations", "Clean unmount tests pass"],
        "priority": "HIGH",
        "estimated_credit_cost": 0.3000,
    }
    m_res = client.post("/api/v1/autonomous/tasks", json=manual_payload, headers=admin_headers)
    assert m_res.status_code == 200, m_res.text
    m_task = m_res.json()
    assert m_task["source"] == "MANUAL"
    assert m_task["priority"] == "HIGH"
    assert float(m_task["estimated_credit_cost"]) == 0.3

    # Bulk import
    bulk_payload = {
        "tasks": [
            {
                "title": "Build Tailwind Landing Hero Section",
                "work_type": "WEBSITE_APP_DEV",
                "description": "Create responsive hero banner with CTA button.",
                "expected_result": "Hero section responsive on mobile and desktop.",
                "priority": "MEDIUM",
                "estimated_credit_cost": 0.1500,
            },
            {
                "title": "Generate AI Feature Explainer Video",
                "work_type": "VIDEO_CREATION",
                "description": "30-second explainer animation of AI features.",
                "expected_result": "1080p MP4 explainer video.",
                "priority": "HIGH",
                "estimated_credit_cost": 0.2500,
            },
        ]
    }
    imp_res = client.post("/api/v1/autonomous/tasks/import", json=bulk_payload, headers=admin_headers)
    assert imp_res.status_code == 200, imp_res.text
    imported = imp_res.json()
    assert len(imported) == 2
    assert imported[0]["source"] == "IMPORTED"
    assert imported[1]["work_type"] == "VIDEO_CREATION"


def test_50_percent_credit_ceiling_guard_and_rotation(autonomous_accounts, db_session):
    """
    Phase 5C: Validates the 50% Planned Usage Ceiling.
    Account A with starting balance $100 has a ceiling of $50.
    Once usage reaches or exceeds $50, Account A must be marked ineligible and rotated out.
    Account B must be chosen as next eligible account.
    """
    acc_a, acc_b = autonomous_accounts
    scheduler = AccountCreditScheduler()

    # Initial state: both have $100 starting balance, ceiling limit $50
    budget_a = scheduler.get_or_create_budget(acc_a.id, db_session)
    budget_b = scheduler.get_or_create_budget(acc_b.id, db_session)
    assert budget_a.is_eligible is True
    assert budget_b.is_eligible is True

    # Consume $49.50 on Account A (still under $50 ceiling)
    scheduler.record_usage_and_release(
        account_id=acc_a.id,
        task_id=1,
        estimated_cost=Decimal("0.0000"),
        actual_cost=Decimal("49.5000"),
        usage_type="PLATFORM_BUILD",
        db=db_session,
    )
    eligible, _ = scheduler.evaluate_account_eligibility(budget_a, db_session)
    assert eligible is True

    # Consume an additional $1.00 on Account A (total: $50.50, exceeds 50% ceiling)
    scheduler.record_usage_and_release(
        account_id=acc_a.id,
        task_id=2,
        estimated_cost=Decimal("0.0000"),
        actual_cost=Decimal("1.0000"),
        usage_type="PLATFORM_BUILD",
        db=db_session,
    )
    eligible, reason = scheduler.evaluate_account_eligibility(budget_a, db_session)
    assert eligible is False
    assert "50% Planned Usage Ceiling reached" in reason

    # Select eligible account for next task: Must rotate to Account B
    selected = scheduler.select_eligible_account(
        work_type="VIDEO_CREATION",
        estimated_cost=Decimal("0.2000"),
        db=db_session,
    )
    assert selected is not None
    selected_acc, selected_budget = selected
    assert selected_acc.id == acc_b.id
    assert selected_budget.account_id == acc_b.id


def test_worker_engine_step_execution_and_checkpoints(autonomous_accounts, client: TestClient, admin_headers: dict, db_session):
    """
    Phase 5B & 5D: Tests end-to-end task progression through multi-step checkpoints
    and verified completion.
    """
    # 1. Start system
    start_res = client.post("/api/v1/autonomous/control", json={"command": "START"}, headers=admin_headers)
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "RUNNING"

    # 2. Create a Website/App task
    task_payload = {
        "title": "Scaffold Enterprise Microservice API",
        "work_type": "WEBSITE_APP_DEV",
        "source": "MANUAL",
        "description": "Generate OpenAPI routes and schema validation.",
        "expected_result": "Working API with automated tests.",
        "acceptance_criteria": ["Clean compile", "Zero test regressions"],
        "priority": "CRITICAL",
        "estimated_credit_cost": 0.3000,
    }
    t_res = client.post("/api/v1/autonomous/tasks", json=task_payload, headers=admin_headers)
    assert t_res.status_code == 200
    task_id = t_res.json()["id"]

    # 3. Step through all 5 checkpoints
    for step_num in range(1, 6):
        step_res = client.post("/api/v1/autonomous/worker/step", headers=admin_headers)
        assert step_res.status_code == 200
        step_data = step_res.json()
        assert "step_completed" in step_data

    # 4. Check final task detail: must be COMPLETED
    detail_res = client.get(f"/api/v1/autonomous/tasks/{task_id}", headers=admin_headers)
    assert detail_res.status_code == 200
    final_task = detail_res.json()
    assert final_task["status"] == "COMPLETED"
    assert final_task["is_mock"] is True
    assert final_task["result_metadata"] is not None

    # Check execution logs
    logs_res = client.get(f"/api/v1/autonomous/tasks/{task_id}/logs", headers=admin_headers)
    assert logs_res.status_code == 200
    logs = logs_res.json()
    assert len(logs) >= 5


def test_system_chat_commands_and_telemetry(autonomous_accounts, client: TestClient, admin_headers: dict):
    """
    Tests conversational chat commands: START, PAUSE, RESUME, STOP, STATUS, ROTATE.
    """
    # Command: STATUS
    res = client.post("/api/v1/autonomous/chat", json={"command_text": "STATUS"}, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["command"] == "STATUS"
    assert "eligible_accounts_count" in data["details"]

    # Command: PAUSE
    res = client.post("/api/v1/autonomous/chat", json={"command_text": "PAUSE"}, headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["system_status"] == "PAUSED"

    # Command: RESUME
    res = client.post("/api/v1/autonomous/chat", json={"command_text": "RESUME"}, headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["system_status"] == "RUNNING"

    # Command: ROTATE
    res = client.post("/api/v1/autonomous/chat", json={"command_text": "ROTATE"}, headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["command"] == "ROTATE"

    # Command: STOP
    res = client.post("/api/v1/autonomous/chat", json={"command_text": "STOP"}, headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["system_status"] == "STOPPED"
