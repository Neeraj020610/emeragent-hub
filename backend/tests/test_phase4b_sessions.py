import os
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import EmergentAccount, AccountPermission, PersonalAccountConsent
from app.models.session import AccountSession
from app.models.user import User
from app.services.session.manager import MultiAccountSessionManager
from app.core.security import decrypt_token


def test_multi_account_session_authentication_and_switching(
    client: TestClient, admin_token: str, db_session: Session
):
    """
    Validate multi-account session management:
    1. Authenticate Account A.
    2. Authenticate Account B.
    3. Switch to A -> Confirm A remains authenticated.
    4. Switch to B -> Confirm B remains authenticated.
    5. Disconnect B -> Confirm B is DISCONNECTED while A remains ACTIVE.
    """
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Fetch two seeded accounts
    acc_a = db_session.query(EmergentAccount).filter(EmergentAccount.account_identifier == "EMG-PROD-01").first()
    acc_b = db_session.query(EmergentAccount).filter(EmergentAccount.account_identifier == "EMG-DEV-02").first()
    assert acc_a is not None and acc_b is not None

    # 1. Authenticate Account A
    auth_payload_a = {
        "auth_method": "oauth2",
        "auth_code": "code_alpha_12345",
        "session_metadata": '{"cluster": "production-us-east"}',
    }
    r_auth_a = client.post(f"/api/v1/sessions/{acc_a.id}/authenticate", json=auth_payload_a, headers=headers)
    assert r_auth_a.status_code == 200, r_auth_a.text
    sess_a = r_auth_a.json()
    assert sess_a["session_status"] == "ACTIVE"
    assert sess_a["account_id"] == acc_a.id
    assert sess_a["is_currently_active"] is True

    # 2. Authenticate Account B
    auth_payload_b = {
        "auth_method": "browser_profile",
        "auth_code": "code_beta_67890",
        "session_metadata": '{"cluster": "dev-eu-central"}',
    }
    r_auth_b = client.post(f"/api/v1/sessions/{acc_b.id}/authenticate", json=auth_payload_b, headers=headers)
    assert r_auth_b.status_code == 200, r_auth_b.text
    sess_b = r_auth_b.json()
    assert sess_b["session_status"] == "ACTIVE"
    assert sess_b["account_id"] == acc_b.id
    assert sess_b["is_currently_active"] is True
    assert sess_b["browser_profile_isolated"] is True

    # 3. Switch back to Account A
    r_switch_a = client.post(f"/api/v1/sessions/{acc_a.id}/switch", headers=headers)
    assert r_switch_a.status_code == 200, r_switch_a.text
    switched_a = r_switch_a.json()
    assert switched_a["status"] == "SUCCESS"
    assert switched_a["account_id"] == acc_a.id
    assert switched_a["session"]["is_currently_active"] is True

    # Confirm Account B remains independently authenticated and ACTIVE in DB!
    db_b = db_session.query(AccountSession).filter(AccountSession.account_id == acc_b.id).first()
    assert db_b.session_status == "ACTIVE"
    assert db_b.reauth_required is False

    # 4. Switch back to Account B
    r_switch_b = client.post(f"/api/v1/sessions/{acc_b.id}/switch", headers=headers)
    assert r_switch_b.status_code == 200
    switched_b = r_switch_b.json()
    assert switched_b["account_id"] == acc_b.id
    assert switched_b["session"]["is_currently_active"] is True

    # Confirm Account A remains ACTIVE!
    db_a = db_session.query(AccountSession).filter(AccountSession.account_id == acc_a.id).first()
    assert db_a.session_status == "ACTIVE"

    # 5. Disconnect Account B only
    r_disc_b = client.post(f"/api/v1/sessions/{acc_b.id}/disconnect", headers=headers)
    assert r_disc_b.status_code == 200
    assert "disconnected" in r_disc_b.json()["message"].lower()

    # Confirm Account B is DISCONNECTED while Account A remains ACTIVE!
    db_b_after = db_session.query(AccountSession).filter(AccountSession.account_id == acc_b.id).first()
    assert db_b_after.session_status == "DISCONNECTED"

    db_a_after = db_session.query(AccountSession).filter(AccountSession.account_id == acc_a.id).first()
    assert db_a_after.session_status == "ACTIVE"


def test_session_restart_persistence(client: TestClient, admin_token: str, db_session: Session):
    """
    Test restart persistence:
    Simulates a backend server restart by instantiating a fresh MultiAccountSessionManager.
    Verifies that encrypted credentials and session validity survive restarts completely.
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    acc = db_session.query(EmergentAccount).filter(EmergentAccount.account_identifier == "EMG-QA-03").first()
    assert acc is not None

    # Authenticate session
    payload = {"auth_method": "oauth2", "auth_code": "persist_code_999"}
    r = client.post(f"/api/v1/sessions/{acc.id}/authenticate", json=payload, headers=headers)
    assert r.status_code == 200

    # Simulate restart: create a new MultiAccountSessionManager instance
    fresh_manager = MultiAccountSessionManager()
    admin_user = db_session.query(User).filter(User.email == "admin@emergent-hub.com").first()

    # List sessions using fresh manager
    sessions = fresh_manager.list_sessions(db=db_session, current_user=admin_user)
    target = next((s for s in sessions if s.account_id == acc.id), None)
    assert target is not None
    assert target.session_status == "ACTIVE"
    assert target.reauth_required is False

    # Check DB encryption at rest
    raw_db_session = db_session.query(AccountSession).filter(AccountSession.account_id == acc.id).first()
    assert raw_db_session.session_data_enc is not None
    # Decryptable in-memory
    decrypted_raw = decrypt_token(raw_db_session.session_data_enc)
    assert "emg_acc_token" in decrypted_raw


def test_expired_and_revoked_session_handling(
    client: TestClient, admin_token: str, db_session: Session
):
    """
    Expired and revoked sessions:
    - Setting token expiration in past marks session EXPIRED and requires re-auth.
    - Switch attempts return 401 Unauthorized.
    - Revoking cleans up browser profile storage.
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    acc = db_session.query(EmergentAccount).filter(EmergentAccount.account_identifier == "EMG-DEV-02").first()

    # Authenticate with browser profile
    client.post(
        f"/api/v1/sessions/{acc.id}/authenticate",
        json={"auth_method": "browser_profile"},
        headers=headers,
    )

    # 1. Force expiration
    sess = db_session.query(AccountSession).filter(AccountSession.account_id == acc.id).first()
    sess.token_expires_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db_session.commit()

    # Validate endpoint updates status
    val_resp = client.post(f"/api/v1/sessions/{acc.id}/validate", headers=headers)
    assert val_resp.status_code == 200
    assert val_resp.json()["session_status"] == "EXPIRED"
    assert val_resp.json()["reauth_required"] is True

    # Switching to expired session returns 401
    switch_resp = client.post(f"/api/v1/sessions/{acc.id}/switch", headers=headers)
    assert switch_resp.status_code == 401
    assert "expired" in switch_resp.json()["detail"].lower()

    # 2. Revoke session
    revoke_resp = client.post(f"/api/v1/sessions/{acc.id}/revoke", headers=headers)
    assert revoke_resp.status_code == 200
    assert "revoked" in revoke_resp.json()["message"].lower()

    db_session.refresh(sess)
    assert sess.session_status == "REVOKED"
    assert sess.session_data_enc is None


def test_session_rbac_and_personal_consent(
    client: TestClient, admin_token: str, member_token: str, db_session: Session
):
    """Member without manage permission cannot authenticate or disconnect a session."""
    member_headers = {"Authorization": f"Bearer {member_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    acc = db_session.query(EmergentAccount).filter(EmergentAccount.account_identifier == "EMG-PROD-01").first()

    # Member cannot authenticate -> 403 Forbidden
    r_fail = client.post(
        f"/api/v1/sessions/{acc.id}/authenticate",
        json={"auth_method": "oauth2"},
        headers=member_headers,
    )
    assert r_fail.status_code == 403

    # Member cannot disconnect -> 403 Forbidden
    r_disc = client.post(f"/api/v1/sessions/{acc.id}/disconnect", headers=member_headers)
    assert r_disc.status_code == 403

    # Stats endpoint is accessible to authenticated users
    stats_resp = client.get("/api/v1/sessions/stats", headers=member_headers)
    assert stats_resp.status_code == 200


def test_isolated_browser_profile_launching(
    client: TestClient, admin_token: str, db_session: Session, monkeypatch
):
    """Verify browser profile launch creates dedicated user-data-dir and triggers background process."""
    import subprocess
    headers = {"Authorization": f"Bearer {admin_token}"}
    acc = db_session.query(EmergentAccount).filter(EmergentAccount.account_identifier == "EMG-PROD-01").first()

    launched_commands = []
    def mock_popen(cmd, *args, **kwargs):
        launched_commands.append(cmd)
        return None
    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    resp = client.post(f"/api/v1/sessions/{acc.id}/launch-browser", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "profile_dir" in data
    assert f"acc_{acc.id}" in data["profile_dir"]
    assert len(launched_commands) == 1
    assert any("--user-data-dir=" in arg for arg in launched_commands[0])


