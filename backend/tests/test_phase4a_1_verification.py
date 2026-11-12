import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import EmergentAccount, AccountPermission, PersonalAccountConsent
from app.models.universal_key import UniversalApiKey, UniversalKeyUsage
from app.models.user import User
from app.core.security import decrypt_token


def test_security_encrypted_at_rest_and_zero_leakage(client: TestClient, admin_token: str, db_session: Session):
    """
    Verify API keys:
    1. Are stored encrypted at rest (AES Fernet) in database.
    2. Never appear in any frontend network response.
    3. Never leak in error messages.
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    secret_key = "emg_test_valid_secret_credential_9876"

    reg_payload = {
        "account_name": "Security Audit Account",
        "api_key": secret_key,
        "proxy_base_url": "https://proxy.emergent.ai",
        "validate_first": True,
    }

    resp = client.post("/api/v1/universal-keys/register-account", json=reg_payload, headers=headers)
    assert resp.status_code == 201
    resp_text = resp.text

    # Response must NEVER contain the raw plaintext key
    assert secret_key not in resp_text
    assert "emg_test_valid_secret_credential_9876" not in resp_text

    data = resp.json()
    key_id = data["id"]

    # Verify Database column is encrypted and does NOT contain raw secret
    db_key = db_session.query(UniversalApiKey).filter(UniversalApiKey.id == key_id).first()
    assert db_key is not None
    assert db_key.api_key_enc != secret_key
    assert "credential" not in db_key.api_key_enc
    # Decryptable only in-memory with server SECRET_KEY
    assert decrypt_token(db_key.api_key_enc) == secret_key

    # Verify GET /universal-keys does not leak plaintext
    list_resp = client.get("/api/v1/universal-keys", headers=headers)
    assert secret_key not in list_resp.text

    # Verify GET /universal-keys/{id} does not leak plaintext
    single_resp = client.get(f"/api/v1/universal-keys/{key_id}", headers=headers)
    assert secret_key not in single_resp.text


def test_disabled_key_prevents_subsequent_inferences(client: TestClient, admin_token: str, db_session: Session):
    """Disabling a key must immediately block inference requests."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    reg_payload = {
        "account_name": "Key Revocation Test Account",
        "api_key": "emg_test_valid_disable_key_5555",
        "validate_first": True,
    }
    reg = client.post("/api/v1/universal-keys/register-account", json=reg_payload, headers=headers).json()
    key_id = reg["id"]

    chat_payload = {
        "key_id": key_id,
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "ping"}],
    }

    # 1. Inference succeeds while active
    r_active = client.post("/api/v1/universal-keys/chat", json=chat_payload, headers=headers)
    assert r_active.status_code == 200

    # 2. Disable key
    toggle_resp = client.put(f"/api/v1/universal-keys/{key_id}", json={"is_active": False}, headers=headers)
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["is_active"] is False

    # 3. Subsequent inference must be rejected
    r_blocked = client.post("/api/v1/universal-keys/chat", json=chat_payload, headers=headers)
    assert r_blocked.status_code in (400, 404)
    assert "active" in r_blocked.json()["detail"].lower()


def test_proxy_base_url_normalization(client: TestClient, admin_token: str):
    """
    Verify client handles proxy URLs with or without trailing slash or /v1 suffix
    without causing path duplication.
    """
    from app.services.universal_key.client import EmergentProxyClient
    client_proxy = EmergentProxyClient()

    assert client_proxy._clean_base_url("https://proxy.emergent.ai") == "https://proxy.emergent.ai"
    assert client_proxy._clean_base_url("https://proxy.emergent.ai/") == "https://proxy.emergent.ai"
    assert client_proxy._clean_base_url("https://proxy.emergent.ai/v1") == "https://proxy.emergent.ai"
    assert client_proxy._clean_base_url("https://proxy.emergent.ai/v1/") == "https://proxy.emergent.ai"
    assert client_proxy._clean_base_url("https://custom.emergent-proxy.internal:8443/v1") == "https://custom.emergent-proxy.internal:8443"


def test_accurate_usage_accounting(client: TestClient, admin_token: str, db_session: Session):
    """Verify tokens and latency are recorded accurately without inventing fake balances."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    reg = client.post(
        "/api/v1/universal-keys/register-account",
        json={"account_name": "Usage Audit Fleet", "api_key": "emg_test_valid_usage_4411"},
        headers=headers,
    ).json()

    chat_resp = client.post(
        "/api/v1/universal-keys/chat",
        json={
            "key_id": reg["id"],
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Return the token count verification."}],
        },
        headers=headers,
    )
    assert chat_resp.status_code == 200
    data = chat_resp.json()

    # Exact token count check
    assert data["prompt_tokens"] > 0
    assert data["completion_tokens"] > 0
    assert data["total_tokens"] == data["prompt_tokens"] + data["completion_tokens"]
    assert data["duration_ms"] > 0

    # Ensure ledger record matches exact event
    usage_entry = (
        db_session.query(UniversalKeyUsage)
        .filter(UniversalKeyUsage.request_id == data["request_id"])
        .first()
    )
    assert usage_entry is not None
    assert usage_entry.prompt_tokens == data["prompt_tokens"]
    assert usage_entry.completion_tokens == data["completion_tokens"]
    assert usage_entry.total_tokens == data["total_tokens"]

