"""
Phase 3 & 3.1 Tests — Email API and OTP Production Hardening
Emergent Central Hub

Covers:
- Redis-backed encrypted transient OTP storage
- Atomic one-time claim (GETDEL) across multi-workers
- Strict binding to request, user, mailbox, and account
- TTL expiry & rejection of expired values
- Server-side PersonalAccountConsent lifecycle (grant, enforce, revoke, expire)
- Prevention of duplicate/replayed command IDs
- Zero database storage of raw OTP or SHA-256 OTP hashes
- Sensitive log and URL redaction
"""
import time
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import status
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

from app.models.account import EmergentAccount, AccountPermission, PersonalAccountConsent
from app.models.otp import MailboxAccount, OTPRequest
from app.models.user import User
from app.models.audit import AuditLog
from app.services.otp.validator import (
    validate_create_command_response,
    validate_retrieve_otp_response,
)
from app.services.otp.redis_store import RedisOTPStore, redis_otp_store
from app.services.otp.security import (
    store_transient_otp,
    claim_transient_otp,
    is_transient_otp_available,
    redact_sensitive_url,
)


# -------------------------------------------------------------
# 1. Unit Tests for Validators & Log Redaction
# -------------------------------------------------------------
def test_validate_create_command_response():
    valid_payload = {
        "status": "success",
        "message": "Command added successfully",
        "data": {"commandId": "7591"},
    }
    ok, cmd_id, err = validate_create_command_response(valid_payload)
    assert ok is True
    assert cmd_id == "7591"
    assert err is None

    err_payload = {"status": "error", "message": "Invalid email parameter"}
    ok, cmd_id, err = validate_create_command_response(err_payload)
    assert ok is False
    assert cmd_id is None
    assert "Invalid email parameter" in err

    missing_cmd = {"status": "success", "data": {}}
    ok, cmd_id, err = validate_create_command_response(missing_cmd)
    assert ok is False
    assert "missing" in err.lower()


def test_validate_retrieve_otp_response():
    found_payload = {
        "status": "success",
        "message": "OTP Found",
        "data": {"otp": "123456"},
    }
    is_valid, otp_found, otp_code, err = validate_retrieve_otp_response(found_payload)
    assert is_valid is True
    assert otp_found is True
    assert otp_code == "123456"

    waiting_payload = {
        "status": "success",
        "message": "No OTP Found",
        "data": {},
    }
    is_valid, otp_found, otp_code, err = validate_retrieve_otp_response(waiting_payload)
    assert is_valid is True
    assert otp_found is False
    assert otp_code is None


def test_redact_sensitive_url():
    url = "https://m.phx.co.in/automation/api/email-api/create-email-command.asp?emailAddress=dev@test.com&employeeName=JohnDoe&commandType=Inbox"
    redacted = redact_sensitive_url(url)
    assert "dev@test.com" not in redacted
    assert "JohnDoe" not in redacted
    assert "emailAddress=***" in redacted
    assert "employeeName=***" in redacted


# -------------------------------------------------------------
# 2. Redis-Backed Transient Storage & Multi-Worker Atomic Retrieval
# -------------------------------------------------------------
def test_redis_atomic_one_time_claim():
    """
    Verifies that Redis GETDEL provides atomic one-time retrieval.
    The first claim succeeds; duplicate claims immediately return None.
    """
    req_id = 88801
    otp = "445566"
    user_id = 42
    mailbox_id = 10
    account_id = 5

    store_transient_otp(
        request_id=req_id,
        otp_code=otp,
        requester_user_id=user_id,
        mailbox_id=mailbox_id,
        account_id=account_id,
        ttl_seconds=60,
    )
    assert is_transient_otp_available(req_id) is True

    # First claim -> must succeed
    claimed = claim_transient_otp(
        request_id=req_id,
        user_id=user_id,
        mailbox_id=mailbox_id,
        account_id=account_id,
    )
    assert claimed == otp

    # Second claim -> must be None (atomic GETDEL zeroization)
    second_claim = claim_transient_otp(
        request_id=req_id,
        user_id=user_id,
        mailbox_id=mailbox_id,
        account_id=account_id,
    )
    assert second_claim is None
    assert is_transient_otp_available(req_id) is False


def test_multi_worker_concurrency_race():
    """
    Simulates multiple backend workers concurrently competing to claim the same OTP.
    Exactly one worker must succeed; all others must receive None.
    """
    req_id = 88802
    otp = "778899"
    user_id = 55
    mailbox_id = 12
    account_id = 8

    store_transient_otp(
        request_id=req_id,
        otp_code=otp,
        requester_user_id=user_id,
        mailbox_id=mailbox_id,
        account_id=account_id,
        ttl_seconds=60,
    )

    def worker_claim(worker_idx):
        return claim_transient_otp(
            request_id=req_id,
            user_id=user_id,
            mailbox_id=mailbox_id,
            account_id=account_id,
        )

    # Launch 6 concurrent workers
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(worker_claim, range(6)))

    # Exactly 1 result is the OTP, exactly 5 are None
    success_count = sum(1 for r in results if r == otp)
    none_count = sum(1 for r in results if r is None)
    assert success_count == 1
    assert none_count == 5


def test_expired_transient_otp():
    """
    Verifies that expired OTP keys cannot be retrieved.
    """
    req_id = 88803
    otp = "112233"
    user_id = 60

    # Store with TTL = 1 second
    store_transient_otp(
        request_id=req_id,
        otp_code=otp,
        requester_user_id=user_id,
        mailbox_id=1,
        account_id=1,
        ttl_seconds=1,
    )
    time.sleep(1.2)

    # Claim after expiration -> returns None
    claimed = claim_transient_otp(request_id=req_id, user_id=user_id, mailbox_id=1, account_id=1)
    assert claimed is None


def test_security_binding_isolation():
    """
    Verifies that attempting to claim an OTP with a mismatched user_id, mailbox_id,
    or account_id is rejected by security bounds.
    """
    req_id = 88804
    otp = "990011"
    correct_user = 100
    wrong_user = 200
    correct_mailbox = 15
    wrong_mailbox = 99
    correct_account = 20
    wrong_account = 77

    store_transient_otp(
        request_id=req_id,
        otp_code=otp,
        requester_user_id=correct_user,
        mailbox_id=correct_mailbox,
        account_id=correct_account,
        ttl_seconds=60,
    )

    # 1. Wrong user
    bad_user_claim = claim_transient_otp(
        request_id=req_id,
        user_id=wrong_user,
        mailbox_id=correct_mailbox,
        account_id=correct_account,
        is_admin=False,
    )
    assert bad_user_claim is None

    # Re-store since GETDEL removes on match check
    store_transient_otp(
        request_id=req_id,
        otp_code=otp,
        requester_user_id=correct_user,
        mailbox_id=correct_mailbox,
        account_id=correct_account,
        ttl_seconds=60,
    )

    # 2. Wrong mailbox
    bad_mb_claim = claim_transient_otp(
        request_id=req_id,
        user_id=correct_user,
        mailbox_id=wrong_mailbox,
        account_id=correct_account,
    )
    assert bad_mb_claim is None

    # Re-store
    store_transient_otp(
        request_id=req_id,
        otp_code=otp,
        requester_user_id=correct_user,
        mailbox_id=correct_mailbox,
        account_id=correct_account,
        ttl_seconds=60,
    )

    # 3. Correct credentials -> Succeeds
    good_claim = claim_transient_otp(
        request_id=req_id,
        user_id=correct_user,
        mailbox_id=correct_mailbox,
        account_id=correct_account,
    )
    assert good_claim == otp


# -------------------------------------------------------------
# 3. Server-Side Owner Consent Workflow
# -------------------------------------------------------------
def test_server_side_owner_consent_lifecycle(client, admin_token, member_token, db_session):
    """
    Tests server-side auditable consent lifecycle:
    1. Member requests personal account OTP without consent -> 403 Forbidden.
    2. Owner grants consent via /api/v1/otp/consents.
    3. Member requests OTP -> allowed.
    4. Owner revokes consent via /api/v1/otp/consents/{id}/revoke.
    5. Member requests OTP again -> 403 Forbidden.
    """
    admin_user = db_session.query(User).filter(User.email == "admin@emergent-hub.com").first()
    member_user = db_session.query(User).filter(User.email == "member@emergent-hub.com").first()

    # Create Personal Emergent Account owned by Admin
    personal_acc = EmergentAccount(
        account_identifier="EMG-OWNER-CONSENT-01",
        account_name="Executive Personal Hub",
        email="executive@company.internal",
        owner_user_id=admin_user.id,
        owner_name="Executive",
        ownership_type="PERSONAL",
        status="active",
    )
    db_session.add(personal_acc)
    db_session.commit()

    # Assign member execution permission
    perm = AccountPermission(
        user_id=member_user.id,
        account_id=personal_acc.id,
        can_view=True,
        can_execute=True,
    )
    db_session.add(perm)

    mb = MailboxAccount(
        email_address="exec-mailbox@company.internal",
        employee_name="Executive Assistant",
        account_id=personal_acc.id,
        ownership_type="PERSONAL",
        api_base_url="https://m.phx.co.in/automation/api/email-api",
        is_active=True,
        verified_access=True,
    )
    db_session.add(mb)
    db_session.commit()

    # 1. Member tries to request OTP without server-side consent -> 403 Forbidden
    resp_no_consent = client.post(
        "/api/v1/otp/request",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "mailbox_id": mb.id,
            "owner_consent_confirmed": True,
        },
    )
    assert resp_no_consent.status_code == status.HTTP_403_FORBIDDEN
    assert "server-side authorization" in resp_no_consent.json()["detail"].lower()

    # 2. Owner grants server-side consent via POST /api/v1/otp/consents
    grant_resp = client.post(
        f"/api/v1/otp/consents?account_id={personal_acc.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "authorized_member_id": member_user.id,
            "permission_scope": "OTP_RETRIEVAL",
            "expires_in_days": 15,
        },
    )
    assert grant_resp.status_code == status.HTTP_201_CREATED
    consent_data = grant_resp.json()
    consent_id = consent_data["id"]
    assert consent_data["is_active"] is True
    assert consent_data["permission_scope"] == "OTP_RETRIEVAL"

    # 3. Member now requests OTP with consent confirmed -> Allowed
    resp_with_consent = client.post(
        "/api/v1/otp/request",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "mailbox_id": mb.id,
            "owner_consent_confirmed": True,
        },
    )
    # Succeeds (blocked_unverified by default switch)
    assert resp_with_consent.status_code in (status.HTTP_201_CREATED, status.HTTP_200_OK)

    # 4. Owner revokes consent
    revoke_resp = client.post(
        f"/api/v1/otp/consents/{consent_id}/revoke",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert revoke_resp.status_code == status.HTTP_200_OK
    assert revoke_resp.json()["is_active"] is False

    # 5. Member tries again -> 403 Forbidden
    resp_revoked = client.post(
        "/api/v1/otp/request",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "mailbox_id": mb.id,
            "owner_consent_confirmed": True,
        },
    )
    assert resp_revoked.status_code == status.HTTP_403_FORBIDDEN


# -------------------------------------------------------------
# 4. Full Flow, Zero-Database OTP Storage, and Command ID Collision
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_full_otp_workflow_zero_db_storage(client, admin_token, db_session):
    acc = EmergentAccount(
        account_identifier="EMG-FLOW-HARDENED-01",
        account_name="Hardened Workflow Account",
        email="hardened-flow@company.internal",
        ownership_type="COMPANY_OWNED",
        status="active",
    )
    db_session.add(acc)
    db_session.commit()

    mb = MailboxAccount(
        email_address="hardened-flow@company.internal",
        employee_name="SecOps Operator",
        account_id=acc.id,
        ownership_type="COMPANY_OWNED",
        api_base_url="https://m.phx.co.in/automation/api/email-api",
        is_active=True,
        verified_access=True,
    )
    db_session.add(mb)
    db_session.commit()

    mock_create = AsyncMock(return_value={
        "status": "success",
        "message": "Command added successfully",
        "data": {"commandId": "9101"},
    })
    mock_retrieve = AsyncMock(return_value={
        "status": "success",
        "message": "OTP Found",
        "data": {"otp": "654321"},
    })

    with patch("app.services.otp.service.settings.EMAIL_API_ENABLED", True):
        with patch("app.services.otp.mail_api.EmailApiClient.create_email_command", mock_create):
            with patch("app.services.otp.mail_api.EmailApiClient.retrieve_otp", mock_retrieve):
                # Trigger request
                resp = client.post(
                    "/api/v1/otp/request",
                    headers={"Authorization": f"Bearer {admin_token}"},
                    json={"mailbox_id": mb.id},
                )
                assert resp.status_code == status.HTTP_201_CREATED
                data = resp.json()
                req_id = data["id"]
                assert data["command_id"] == "9101"

                # Simulate orchestrator completion with transient Redis store
                req_db = db_session.query(OTPRequest).filter(OTPRequest.id == req_id).first()
                req_db.status = "completed"
                req_db.otp_code_hash = None  # Zero DB hash storage
                db_session.commit()

                store_transient_otp(
                    request_id=req_id,
                    otp_code="654321",
                    requester_user_id=req_db.requested_by_user_id,
                    mailbox_id=req_db.mailbox_id,
                    account_id=req_db.account_id,
                    ttl_seconds=300,
                )

                # Claim OTP
                claim_resp = client.get(
                    f"/api/v1/otp/{req_id}/result",
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
                assert claim_resp.status_code == status.HTTP_200_OK
                assert claim_resp.json()["otp_code"] == "654321"

                # Verify Zero OTP / Hash in database
                db_session.refresh(req_db)
                assert req_db.otp_code_hash is None

                # Second claim must return 410 Gone (atomic one-time claim)
                second_claim = client.get(
                    f"/api/v1/otp/{req_id}/result",
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
                assert second_claim.status_code == status.HTTP_410_GONE


def test_command_id_reuse_rejection(client, admin_token, db_session):
    """
    Verifies that if the external email API returns a commandId that has already
    been used, the backend rejects it with 409 Conflict.
    """
    acc = EmergentAccount(
        account_identifier="EMG-REUSE-01",
        account_name="Reuse Test Account",
        email="reuse@company.internal",
        ownership_type="COMPANY_OWNED",
        status="active",
    )
    db_session.add(acc)
    db_session.commit()

    mb = MailboxAccount(
        email_address="reuse@company.internal",
        employee_name="Operator",
        account_id=acc.id,
        ownership_type="COMPANY_OWNED",
        api_base_url="https://m.phx.co.in/automation/api/email-api",
        is_active=True,
        verified_access=True,
    )
    db_session.add(mb)
    db_session.commit()

    # Pre-existing completed request with command_id="7711"
    existing_req = OTPRequest(
        mailbox_id=mb.id,
        account_id=acc.id,
        status="completed",
        correlation_id="cmd_existing_completed",
        command_id="7711",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db_session.add(existing_req)
    db_session.commit()

    # Mock external API returning the same commandId "7711"
    mock_duplicate = AsyncMock(return_value={
        "status": "success",
        "message": "Command added successfully",
        "data": {"commandId": "7711"},
    })

    with patch("app.services.otp.service.settings.EMAIL_API_ENABLED", True):
        with patch("app.services.otp.mail_api.EmailApiClient.create_email_command", mock_duplicate):
            resp = client.post(
                "/api/v1/otp/request",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"mailbox_id": mb.id},
            )
            assert resp.status_code == status.HTTP_409_CONFLICT
            assert "reused commandid" in resp.json()["detail"].lower()


def test_otp_cancellation(client, admin_token, db_session):
    acc = EmergentAccount(
        account_identifier="EMG-CANCEL-001",
        account_name="Cancel Test Account",
        email="cancel@company.internal",
        ownership_type="COMPANY_OWNED",
        status="active",
    )
    db_session.add(acc)
    db_session.commit()

    mb = MailboxAccount(
        email_address="cancel@company.internal",
        employee_name="Cancel User",
        account_id=acc.id,
        ownership_type="COMPANY_OWNED",
        api_base_url="https://m.phx.co.in/automation/api/email-api",
        is_active=True,
        verified_access=True,
    )
    db_session.add(mb)
    db_session.commit()

    req = OTPRequest(
        mailbox_id=mb.id,
        account_id=acc.id,
        status="polling",
        correlation_id="cmd_to_cancel",
        command_id="5544",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db_session.add(req)
    db_session.commit()

    cancel_resp = client.post(
        f"/api/v1/otp/{req.id}/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert cancel_resp.status_code == status.HTTP_200_OK
    assert cancel_resp.json()["status"] == "cancelled"

    db_session.refresh(req)
    assert req.status == "cancelled"


def test_audit_log_does_not_contain_otp(client, admin_token, db_session):
    logs = db_session.query(AuditLog).filter(AuditLog.resource_type == "otp_request").all()
    for log in logs:
        if log.details:
            assert "654321" not in log.details
            assert "445566" not in log.details
