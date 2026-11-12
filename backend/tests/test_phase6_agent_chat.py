import io
import json
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.models.user import User
from app.models.account import EmergentAccount
from app.models.session import AccountSession
from app.models.autonomous import AutonomousTask, AccountCreditBudget
from app.models.chat import Conversation, ConversationMessage, MessageAttachment
from app.services.autonomous.scheduler import AccountCreditScheduler


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def chat_test_account(db_session):
    """Sets up an eligible account with an active session and 50% ceiling budget."""
    admin_user = db_session.query(User).filter(User.email == settings.INITIAL_ADMIN_EMAIL).first()
    acc = EmergentAccount(
        account_identifier="ACC-CHAT-PROD-001",
        account_name="Agent Chat Execution Account",
        email="chat-agent@emergent.sh",
        ownership_type="COMPANY_OWNED",
        owner_user_id=admin_user.id if admin_user else None,
        status="active",
        connection_status="CONNECTED",
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)

    sess = AccountSession(
        account_id=acc.id,
        session_token="sess-token-chat-test",
        auth_method="browser_profile",
        session_status="ACTIVE",
    )
    db_session.add(sess)
    db_session.commit()

    scheduler = AccountCreditScheduler()
    scheduler.update_account_budget(
        account_id=acc.id,
        starting_balance=Decimal("200.0000"),
        ceiling_percentage=Decimal("50.00"),
        balance_source="API_VERIFIED",
        db=db_session,
    )
    return acc


def test_conversation_lifecycle(client: TestClient, admin_headers: dict):
    """
    Phase 6: Creates new conversation, verifies initial greeting, lists conversations,
    and tests deletion.
    """
    # 1. Create conversation
    res = client.post("/api/v1/agent-chat/conversations", json={"title": "Test AI Chat Session"}, headers=admin_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["conversation_uuid"] is not None
    assert data["title"] == "Test AI Chat Session"
    assert len(data["messages"]) == 1
    assert data["messages"][0]["sender_type"] == "AGENT"
    conv_uuid = data["conversation_uuid"]

    # 2. List conversations
    list_res = client.get("/api/v1/agent-chat/conversations", headers=admin_headers)
    assert list_res.status_code == 200
    conv_list = list_res.json()
    assert any(c["conversation_uuid"] == conv_uuid for c in conv_list)

    # 3. Get detail
    detail_res = client.get(f"/api/v1/agent-chat/conversations/{conv_uuid}", headers=admin_headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["conversation_uuid"] == conv_uuid

    # 4. Delete conversation
    del_res = client.delete(f"/api/v1/agent-chat/conversations/{conv_uuid}", headers=admin_headers)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"

    # Verify 404 after deletion
    get_after_del = client.get(f"/api/v1/agent-chat/conversations/{conv_uuid}", headers=admin_headers)
    assert get_after_del.status_code == 404


def test_attachment_upload_and_inspection(client: TestClient, admin_headers: dict):
    """
    Phase 6: Tests genuine file upload, storage on disk, content inspection,
    and RBAC-protected download.
    """
    # Create conversation
    conv_res = client.post("/api/v1/agent-chat/conversations", json={"title": "Attachment Test"}, headers=admin_headers)
    conv_uuid = conv_res.json()["conversation_uuid"]

    # Upload mock source code file
    file_content = b"def calculate_total(a: int, b: int) -> int:\n    return a + b\n"
    files = {"file": ("calculator.py", io.BytesIO(file_content), "text/x-python")}
    upload_res = client.post(f"/api/v1/agent-chat/conversations/{conv_uuid}/upload", files=files, headers=admin_headers)
    assert upload_res.status_code == 200, upload_res.text
    att_data = upload_res.json()
    assert att_data["file_name"] == "calculator.py"
    assert att_data["file_size_bytes"] == len(file_content)
    assert "lines" in att_data["file_summary"]
    att_id = att_data["id"]

    # Download file back
    down_res = client.get(f"/api/v1/agent-chat/attachments/{att_id}/download", headers=admin_headers)
    assert down_res.status_code == 200
    assert down_res.content == file_content


def test_agent_chat_ambiguous_prompt_clarification(client: TestClient, admin_headers: dict):
    """
    Phase 6: Verifies agent asks clarifying questions when user prompt is ambiguous or lacks details.
    """
    conv_res = client.post("/api/v1/agent-chat/conversations", json={"title": "Clarification Test"}, headers=admin_headers)
    conv_uuid = conv_res.json()["conversation_uuid"]

    res = client.post(
        f"/api/v1/agent-chat/conversations/{conv_uuid}/messages",
        json={"prompt": "hello, I want to create something"},
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    reply = res.json()
    assert reply["sender_type"] == "AGENT"
    assert reply["execution_status"] == "WAITING_INPUT"
    assert "clarify" in reply["content"].lower()


def test_agent_chat_video_task_planning_and_execution(chat_test_account, client: TestClient, admin_headers: dict):
    """
    Phase 6: Tests natural language video task request.
    Verifies agent understands intent, builds plan with acceptance criteria,
    selects eligible Emergent account under 50% credit ceiling, and executes initial checkpoints.
    """
    conv_res = client.post("/api/v1/agent-chat/conversations", json={"title": "Video Pipeline Chat"}, headers=admin_headers)
    conv_uuid = conv_res.json()["conversation_uuid"]

    prompt = "Create a 20-second high-energy product video for Emergent Central Hub with scene script, storyboard, and voiceover."
    res = client.post(
        f"/api/v1/agent-chat/conversations/{conv_uuid}/messages",
        json={"prompt": prompt, "auto_execute": True},
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    reply = res.json()
    assert reply["sender_type"] == "AGENT"
    assert reply["task_id"] is not None
    assert reply["action_plan_json"] is not None
    assert reply["is_mock"] is True  # Transparent MOCK attribution
    assert "Acceptance Criteria" in reply["content"]
    assert "Assigned Account" in reply["content"]


def test_agent_chat_task_controls_stop_pause_resume(chat_test_account, client: TestClient, admin_headers: dict, db_session):
    """
    Phase 6: Tests task controls (PAUSE, RESUME, STOP) from within the conversation.
    """
    conv_res = client.post("/api/v1/agent-chat/conversations", json={"title": "Control Test"}, headers=admin_headers)
    conv_uuid = conv_res.json()["conversation_uuid"]

    # Submit app task
    prompt = "Build a responsive Next.js landing page with auth routes and clean components."
    res = client.post(
        f"/api/v1/agent-chat/conversations/{conv_uuid}/messages",
        json={"prompt": prompt, "auto_execute": False},
        headers=admin_headers,
    )
    assert res.status_code == 200
    task_id = res.json()["task_id"]

    # PAUSE
    pause_res = client.post(
        f"/api/v1/agent-chat/conversations/{conv_uuid}/control",
        json={"action": "PAUSE", "note": "Pausing for requirements review"},
        headers=admin_headers,
    )
    assert pause_res.status_code == 200
    assert pause_res.json()["status"] == "PAUSED"

    # RESUME
    resume_res = client.post(
        f"/api/v1/agent-chat/conversations/{conv_uuid}/control",
        json={"action": "RESUME"},
        headers=admin_headers,
    )
    assert resume_res.status_code == 200
    assert resume_res.json()["status"] == "QUEUED"

    # STOP
    stop_res = client.post(
        f"/api/v1/agent-chat/conversations/{conv_uuid}/control",
        json={"action": "STOP", "note": "Cancelled by operator"},
        headers=admin_headers,
    )
    assert stop_res.status_code == 200
    assert stop_res.json()["status"] == "CANCELLED"

