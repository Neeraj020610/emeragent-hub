import io
from app.models.user import User


def test_manual_credit_entry(client, admin_token):
    acc_res = client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {admin_token}"})
    account_id = acc_res.json()[0]["id"]

    payload = {
        "account_id": account_id,
        "available_credits": 2500.50,
        "consumed_credits": 120.25,
        "total_allocated": 3000.00,
        "notes": "Q4 Enterprise Credit Injection",
    }
    response = client.post(
        "/api/v1/credits/manual",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    snap = response.json()
    assert float(snap["available_credits"]) == 2500.50
    assert snap["balance_source"] == "manual"


def test_csv_import_credits(client, admin_token):
    csv_content = (
        "account_identifier,available_credits,consumed_credits,total_allocated\n"
        "EMG-PROD-01,1500.0000,50.0000,2000.0000\n"
        "EMG-DEV-02,800.0000,20.0000,1000.0000\n"
    )
    file_tuple = ("credits.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")
    response = client.post(
        "/api/v1/credits/import-csv",
        files={"file": file_tuple},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["successful_imports"] == 2
    assert data["failed_rows"] == 0


def test_build_job_creation(client, member_token, admin_token, db_session):
    member_user = db_session.query(User).filter(User.email == "member@emergent-hub.com").first()
    # Admin creates project first with member assigned
    acc_res = client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {admin_token}"})
    account_id = acc_res.json()[0]["id"]

    proj_payload = {
        "account_id": account_id,
        "project_name": "Autonomous Agent Workspace",
        "project_key": "AGNT",
        "description": "Agent orchestration pipeline",
        "status": "active",
        "member_user_ids": [member_user.id],
    }
    proj_res = client.post(
        "/api/v1/projects",
        json=proj_payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # Member submits build job
    job_payload = {
        "project_id": project_id,
        "account_id": account_id,
        "job_type": "full_stack",
        "request_payload": '{"goal": "Build CRM dashboard"}',
    }
    job_res = client.post(
        "/api/v1/jobs",
        json=job_payload,
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert job_res.status_code == 201
    job = job_res.json()
    assert job["job_status"] in ("pending", "QUEUED", "DRAFT")
    assert job["project_id"] == project_id


def test_usage_summary_metrics(client, admin_token):
    response = client.get("/api/v1/reports/summary", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    data = response.json()
    assert "total_accounts" in data
    assert "connected_accounts" in data
    assert "disconnected_accounts" in data
    assert "total_available_credits" in data
    assert "today_consumption" in data
    assert "monthly_consumption" in data
    assert "active_build_jobs" in data
    assert "failed_build_jobs" in data
    assert len(data["consumption_trend"]) == 7
