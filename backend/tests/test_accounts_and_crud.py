def test_list_accounts_admin(client, admin_token):
    response = client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    accounts = response.json()
    assert len(accounts) >= 3
    identifiers = [a["account_identifier"] for a in accounts]
    assert "EMG-PROD-01" in identifiers


def test_create_account_admin(client, admin_token):
    payload = {
        "account_identifier": "EMG-RESEARCH-05",
        "account_name": "Deep Learning Research Node",
        "email": "research@emergent-hub.com",
        "organization": "Emergent Advanced Labs",
        "status": "active",
        "auth_type": "oauth",
        "connection_status": "disconnected",
    }
    response = client.post(
        "/api/v1/accounts",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    created = response.json()
    assert created["account_identifier"] == "EMG-RESEARCH-05"
    assert created["account_name"] == "Deep Learning Research Node"


def test_create_account_duplicate_rejected(client, admin_token):
    payload = {
        "account_identifier": "EMG-PROD-01",  # Already exists
        "account_name": "Duplicate Prod Account",
        "email": "duplicate@emergent-hub.com",
    }
    response = client.post(
        "/api/v1/accounts",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_update_account(client, admin_token):
    # Retrieve first account
    list_res = client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {admin_token}"})
    acc_id = list_res.json()[0]["id"]

    update_payload = {"account_name": "Updated Production Cluster"}
    res = client.put(
        f"/api/v1/accounts/{acc_id}",
        json=update_payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["account_name"] == "Updated Production Cluster"


def test_account_sync_endpoint(client, admin_token):
    list_res = client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {admin_token}"})
    acc_id = list_res.json()[0]["id"]

    res = client.post(
        f"/api/v1/accounts/{acc_id}/sync",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "sync_result" in data
    assert data["sync_result"]["status"] == "ready_for_credentials"
