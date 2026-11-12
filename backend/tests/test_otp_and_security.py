def test_mailbox_security_default_unverified(client, admin_token):
    res = client.get("/api/v1/otp/mailboxes", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    mailboxes = res.json()
    assert len(mailboxes) >= 1
    # Check default verified_access is False
    assert mailboxes[0]["verified_access"] is False


def test_otp_request_correlation(client, admin_token):
    res = client.get("/api/v1/otp/mailboxes", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    mailboxes = res.json()
    assert len(mailboxes) > 0
    mailbox_id = mailboxes[0]["id"]

    otp_payload = {
        "mailbox_id": mailbox_id,
        "sender_filter": "auth@emergent.ai",
        "subject_filter": "Your Verification Code",
        "validity_minutes": 15,
    }
    otp_res = client.post(
        "/api/v1/otp/request",
        json=otp_payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert otp_res.status_code == 201
    data = otp_res.json()
    assert "correlation_id" in data
    assert data["correlation_id"].startswith("cmd_")


def test_audit_logs_recorded(client, admin_token):
    # Perform an audited action
    res_sync = client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {admin_token}"})
    acc_id = res_sync.json()[0]["id"]
    client.post(f"/api/v1/accounts/{acc_id}/sync", headers={"Authorization": f"Bearer {admin_token}"})

    res = client.get("/api/v1/audit", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    logs = res.json()
    assert len(logs) > 0
    actions = [l["action"] for l in logs]
    assert any("account_synced" in a for a in actions)
