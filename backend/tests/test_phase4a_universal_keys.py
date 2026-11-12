import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import EmergentAccount, AccountPermission, PersonalAccountConsent
from app.models.universal_key import UniversalApiKey, UniversalKeyUsage
from app.core.security import decrypt_token


def test_universal_key_account_registration_no_email(client: TestClient, admin_token: str, db_session: Session):
    """
    Direct registration of Emergent account using ONLY:
    - Account Display Name (required)
    - Universal API Key (required)
    - No email login, no email password, no OTP.
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "account_name": "LiteLLM API Production Fleet",
        "api_key": "emg_test_valid_prod_key_9988",
        "proxy_base_url": "https://proxy.emergent.ai",
        "validate_first": True,
    }

    resp = client.post("/api/v1/universal-keys/register-account", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()

    # Check key response format
    assert data["account_name"] == "LiteLLM API Production Fleet"
    assert data["key_name"] == "LiteLLM API Production Fleet Primary Key"
    assert "masked_key" in data
    # Plaintext key should NOT be returned
    assert "emg_test_valid_prod_key_9988" not in str(data)
    assert data["masked_key"].startswith("emg_test")
    assert data["masked_key"].endswith("9988")
    assert data["validation_status"] == "VALID"
    assert data["last_validated_at"] is not None

    # Check account in database
    acc = db_session.query(EmergentAccount).filter(EmergentAccount.id == data["account_id"]).first()
    assert acc is not None
    assert acc.auth_type == "universal_key"
    # Clearly distinguished from workspace accounts
    assert acc.connection_status == "API_CONNECTED"
    assert acc.email is None  # optional email was omitted

    # Check encryption at rest
    key_db = db_session.query(UniversalApiKey).filter(UniversalApiKey.id == data["id"]).first()
    assert key_db is not None
    assert key_db.api_key_enc != "emg_test_valid_prod_key_9988"
    assert decrypt_token(key_db.api_key_enc) == "emg_test_valid_prod_key_9988"


def test_universal_key_account_registration_with_optional_email_metadata(
    client: TestClient, admin_token: str, db_session: Session
):
    """Email metadata is optional and stored as metadata without requiring email login."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "account_name": "API Lab With Alert Email",
        "api_key": "emg_test_valid_alert_key_1122",
        "email": "alerts-billing@company.org",
        "description": "Used for LLM inference pipelines with alert routing",
        "proxy_base_url": "https://proxy.emergent.ai",
        "validate_first": True,
    }

    resp = client.post("/api/v1/universal-keys/register-account", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["account_email"] == "alerts-billing@company.org"

    acc = db_session.query(EmergentAccount).filter(EmergentAccount.id == data["account_id"]).first()
    assert acc.email == "alerts-billing@company.org"
    assert acc.auth_type == "universal_key"
    assert acc.connection_status == "API_CONNECTED"


def test_universal_key_validation_failure_rejects_registration(
    client: TestClient, admin_token: str, db_session: Session
):
    """If proxy validation fails (e.g. 401 Unauthorized), account must NOT be registered."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "account_name": "Invalid Key Account",
        "api_key": "emg_test_invalid_bogus_key_0000",
        "validate_first": True,
    }

    resp = client.post("/api/v1/universal-keys/register-account", json=payload, headers=headers)
    assert resp.status_code == 400
    assert "validation failed" in resp.json()["detail"].lower()

    # Ensure no account was created
    acc = db_session.query(EmergentAccount).filter(EmergentAccount.account_name == "Invalid Key Account").first()
    assert acc is None


def test_universal_key_support_multiple_independent_keys(
    client: TestClient, admin_token: str, db_session: Session
):
    """Central Hub must support multiple independent Universal API Keys per account and across accounts."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Register initial account with key
    p1 = {
        "account_name": "Multi-Key Account",
        "api_key": "emg_test_valid_key1_1234",
    }
    r1 = client.post("/api/v1/universal-keys/register-account", json=p1, headers=headers)
    assert r1.status_code == 201
    acc_id = r1.json()["account_id"]

    # Add second key to same account
    p2 = {
        "account_id": acc_id,
        "key_name": "Multi-Key Secondary Backup",
        "api_key": "emg_test_valid_key2_5678",
    }
    r2 = client.post("/api/v1/universal-keys", json=p2, headers=headers)
    assert r2.status_code == 201
    k2 = r2.json()
    assert k2["key_last4"] == "5678"

    # List keys for this account
    r_list = client.get(f"/api/v1/universal-keys?account_id={acc_id}", headers=headers)
    assert r_list.status_code == 200
    keys = r_list.json()
    assert len(keys) == 2


def test_universal_key_management_update_reconnect_delete(
    client: TestClient, admin_token: str, db_session: Session
):
    """Allow updating, disabling, reconnecting, and deleting API keys."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    p = {
        "account_name": "Lifecycle Management Account",
        "api_key": "emg_test_valid_manage_4321",
    }
    reg = client.post("/api/v1/universal-keys/register-account", json=p, headers=headers).json()
    key_id = reg["id"]
    acc_id = reg["account_id"]

    # 1. Update key name & disable
    up_resp = client.put(
        f"/api/v1/universal-keys/{key_id}",
        json={"key_name": "Renamed Primary Key", "is_active": False},
        headers=headers,
    )
    assert up_resp.status_code == 200
    assert up_resp.json()["key_name"] == "Renamed Primary Key"
    assert up_resp.json()["is_active"] is False

    # 2. Re-enable
    up_resp2 = client.put(f"/api/v1/universal-keys/{key_id}", json={"is_active": True}, headers=headers)
    assert up_resp2.status_code == 200
    assert up_resp2.json()["is_active"] is True

    # 3. Re-validate (reconnect test)
    val_resp = client.post(f"/api/v1/universal-keys/{key_id}/validate", headers=headers)
    assert val_resp.status_code == 200
    assert val_resp.json()["is_valid"] is True

    # 4. Delete key
    del_resp = client.delete(f"/api/v1/universal-keys/{key_id}", headers=headers)
    assert del_resp.status_code == 200
    assert "deleted successfully" in del_resp.json()["message"]

    # Account connection status reflects no active keys
    acc = db_session.query(EmergentAccount).filter(EmergentAccount.id == acc_id).first()
    assert acc.connection_status == "DISCONNECTED"


def test_universal_key_rbac_member_restrictions(
    client: TestClient, member_token: str, admin_token: str
):
    """Regular member cannot register accounts or delete keys."""
    member_headers = {"Authorization": f"Bearer {member_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Member attempt registration -> 403 Forbidden
    payload = {
        "account_name": "Unauthorized Member Fleet",
        "api_key": "emg_test_valid_member_key_1111",
    }
    resp = client.post("/api/v1/universal-keys/register-account", json=payload, headers=member_headers)
    assert resp.status_code == 403

    # Admin registers key
    reg_resp = client.post("/api/v1/universal-keys/register-account", json=payload, headers=admin_headers)
    assert reg_resp.status_code == 201
    key_id = reg_resp.json()["id"]

    # Member attempt deletion -> 403 Forbidden
    del_resp = client.delete(f"/api/v1/universal-keys/{key_id}", headers=member_headers)
    assert del_resp.status_code == 403


def test_universal_key_inference_chat_and_usage_ledger(
    client: TestClient, admin_token: str, db_session: Session
):
    """
    Execute chat inference through LiteLLM proxy gateway:
    - Captures tokens, latency, cost.
    - Records usage event in universal_key_usage_events.
    - Connects usage to the exact registered account.
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    p = {
        "account_name": "Inference Ledger Account",
        "api_key": "emg_test_valid_chat_7777",
    }
    reg = client.post("/api/v1/universal-keys/register-account", json=p, headers=headers).json()
    key_id = reg["id"]
    acc_id = reg["account_id"]

    chat_payload = {
        "key_id": key_id,
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a helpful coding assistant."},
            {"role": "user", "content": "What is 2 + 2?"},
        ],
        "temperature": 0.5,
        "max_tokens": 100,
    }

    chat_resp = client.post("/api/v1/universal-keys/chat", json=chat_payload, headers=headers)
    assert chat_resp.status_code == 200, chat_resp.text
    chat_data = chat_resp.json()

    assert chat_data["status"] == "SUCCESS"
    assert chat_data["total_tokens"] > 0
    assert chat_data["account_id"] == acc_id
    assert chat_data["key_id"] == key_id
    assert "Emergent Proxy Response" in chat_data["content"]

    # Check usage ledger in DB
    usage_rec = (
        db_session.query(UniversalKeyUsage)
        .filter(UniversalKeyUsage.key_id == key_id)
        .order_by(UniversalKeyUsage.created_at.desc())
        .first()
    )
    assert usage_rec is not None
    assert usage_rec.account_id == acc_id
    assert usage_rec.total_tokens == chat_data["total_tokens"]
    assert usage_rec.duration_ms > 0

    # Check usage ledger endpoint
    ledger_resp = client.get(f"/api/v1/universal-keys/usage?account_id={acc_id}", headers=headers)
    assert ledger_resp.status_code == 200
    ledger_items = ledger_resp.json()
    assert len(ledger_items) >= 1
    assert ledger_items[0]["account_name"] == "Inference Ledger Account"

    # Check stats endpoint
    stats_resp = client.get("/api/v1/universal-keys/stats", headers=headers)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_requests"] >= 1
    assert stats["total_tokens"] >= chat_data["total_tokens"]


def test_universal_key_personal_account_consent_enforcement(
    client: TestClient, admin_token: str, member_token: str, db_session: Session
):
    """
    On PERSONAL accounts, an assigned member requires explicit PersonalAccountConsent
    to execute LLM inferences.
    """
    from app.models.user import User
    member_user = db_session.query(User).filter(User.email == "member@emergent-hub.com").first()
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    member_headers = {"Authorization": f"Bearer {member_token}"}

    # Admin registers a PERSONAL account
    payload = {
        "account_name": "Private Personal Workspace",
        "api_key": "emg_test_valid_personal_5544",
        "ownership_type": "PERSONAL",
    }
    reg = client.post("/api/v1/universal-keys/register-account", json=payload, headers=admin_headers).json()
    acc_id = reg["account_id"]
    key_id = reg["id"]

    # Grant member execute permission on account
    perm = AccountPermission(
        user_id=member_user.id,
        account_id=acc_id,
        can_view=True,
        can_execute=True,
        can_manage=False,
    )
    db_session.add(perm)
    db_session.commit()

    chat_payload = {
        "account_id": acc_id,
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Hello world"}],
    }

    # Member attempt without PersonalAccountConsent -> 403 Forbidden
    r_fail = client.post("/api/v1/universal-keys/chat", json=chat_payload, headers=member_headers)
    assert r_fail.status_code == 403
    assert "personal account consent" in r_fail.json()["detail"].lower()

    # Now grant explicit personal account consent
    consent = PersonalAccountConsent(
        account_id=acc_id,
        owner_user_id=member_user.id, # owner or admin grant
        authorized_member_id=member_user.id,
        permission_scope="LLM_EXECUTION",
        is_active=True,
    )
    db_session.add(consent)
    db_session.commit()

    # Member attempt with consent -> 200 OK
    r_ok = client.post("/api/v1/universal-keys/chat", json=chat_payload, headers=member_headers)
    assert r_ok.status_code == 200
    assert r_ok.json()["status"] == "SUCCESS"
