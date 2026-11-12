from datetime import datetime, timezone
import pytest
from app.core.security import encrypt_token, decrypt_token
from app.models.account import EmergentAccount, AccountConnection


def test_token_encryption_fernet():
    plain_token = "emg_secret_oauth_access_token_xyz987"
    encrypted = encrypt_token(plain_token)
    
    assert encrypted != plain_token
    assert not plain_token in encrypted
    decrypted = decrypt_token(encrypted)
    assert decrypted == plain_token


def test_create_account_with_ownership(client, admin_token):
    payload = {
        "account_identifier": "EMG-OWNER-01",
        "account_name": "Core Enterprise Node",
        "email": "core-enterprise@emergent-hub.com",
        "organization": "Platform Infrastructure",
        "ownership_type": "COMPANY_OWNED",
        "description": "High-throughput cluster for core builds",
        "status": "active",
        "auth_type": "oauth",
    }
    response = client.post(
        "/api/v1/accounts",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["account_identifier"] == "EMG-OWNER-01"
    assert data["ownership_type"] == "COMPANY_OWNED"
    assert data["connection_status"] == "DISCONNECTED"
    assert data["assigned_members_count"] >= 1


def test_create_personal_account(client, manager_token):
    payload = {
        "account_identifier": "EMG-PERS-02",
        "account_name": "Personal AI Sandbox",
        "email": "manager-personal@emergent-hub.com",
        "ownership_type": "PERSONAL",
        "description": "Personal account isolated to owner",
        "status": "active",
        "auth_type": "oauth",
    }
    response = client.post(
        "/api/v1/accounts",
        json=payload,
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["ownership_type"] == "PERSONAL"


def test_member_assignment_and_revocation(client, admin_token):
    # Retrieve first account
    list_res = client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {admin_token}"})
    account_id = list_res.json()[0]["id"]

    # Assign team member (user_id=3)
    assign_payload = {
        "user_id": 3,
        "can_view": True,
        "can_execute": True,
        "can_manage": False,
    }
    assign_res = client.post(
        f"/api/v1/accounts/{account_id}/members",
        json=assign_payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert assign_res.status_code == 201
    member_data = assign_res.json()
    assert member_data["user_id"] == 3
    assert member_data["can_execute"] is True

    # List members
    members_res = client.get(
        f"/api/v1/accounts/{account_id}/members",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert members_res.status_code == 200
    m_list = members_res.json()
    assert any(m["user_id"] == 3 for m in m_list)

    # Revoke member
    del_res = client.delete(
        f"/api/v1/accounts/{account_id}/members/3",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert del_res.status_code == 204


def test_personal_account_authorization_isolation(client, manager_token, member_token):
    # Manager creates personal account
    payload = {
        "account_identifier": "EMG-SECURE-PERS",
        "account_name": "Manager Isolated Node",
        "email": "isolated@emergent-hub.com",
        "ownership_type": "PERSONAL",
    }
    create_res = client.post(
        "/api/v1/accounts",
        json=payload,
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    account_id = create_res.json()["id"]

    # A regular member attempts to assign someone else to this personal account -> Forbidden
    assign_payload = {
        "user_id": 1,
        "can_view": True,
    }
    assign_res = client.post(
        f"/api/v1/accounts/{account_id}/members",
        json=assign_payload,
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert assign_res.status_code == 403


def test_connection_lifecycle(client, admin_token):
    # Retrieve an account
    list_res = client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {admin_token}"})
    account_id = list_res.json()[0]["id"]

    # 1. Connect without auth_code -> status PENDING (awaiting OAuth)
    pending_conn = client.post(
        f"/api/v1/accounts/{account_id}/connect",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert pending_conn.status_code == 200
    assert pending_conn.json()["status"] == "PENDING"

    # 2. Connect with auth_code -> status CONNECTED & tokens encrypted
    conn_res = client.post(
        f"/api/v1/accounts/{account_id}/connect?auth_code=test_oauth_code_12345",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert conn_res.status_code == 200
    assert conn_res.json()["status"] == "CONNECTED"

    # 3. Check connection health
    health_res = client.get(
        f"/api/v1/accounts/{account_id}/connection",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "CONNECTED"
    assert health_res.json()["has_access_token"] is True

    # 4. Reconnect
    recon_res = client.post(
        f"/api/v1/accounts/{account_id}/reconnect",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert recon_res.status_code == 200
    assert recon_res.json()["status"] == "CONNECTED"

    # 5. Disconnect
    disc_res = client.post(
        f"/api/v1/accounts/{account_id}/disconnect",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert disc_res.status_code == 200
    assert disc_res.json()["status"] == "DISCONNECTED"


def test_member_cannot_delete_or_disconnect(client, member_token, admin_token):
    list_res = client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {admin_token}"})
    account_id = list_res.json()[0]["id"]

    # Member attempts delete -> 403 Forbidden
    del_res = client.delete(
        f"/api/v1/accounts/{account_id}",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert del_res.status_code == 403

    # Member attempts disconnect -> 403 Forbidden
    disc_res = client.post(
        f"/api/v1/accounts/{account_id}/disconnect",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert disc_res.status_code == 403


def test_account_activity_log(client, admin_token):
    list_res = client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {admin_token}"})
    account_id = list_res.json()[0]["id"]

    act_res = client.get(
        f"/api/v1/accounts/{account_id}/activity",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert act_res.status_code == 200
    logs = act_res.json()
    assert isinstance(logs, list)

