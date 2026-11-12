"""
Phase 3.2 Tests — Redis Fail-Closed Reliability, Storage Hardening, and Server-Side Consent
Emergent Central Hub
"""
import time
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import status
from datetime import datetime, timezone, timedelta
from sqlalchemy.exc import IntegrityError

import redis
import fakeredis
from app.models.account import EmergentAccount, AccountPermission, PersonalAccountConsent
from app.models.otp import MailboxAccount, OTPRequest
from app.models.user import User
from app.models.audit import AuditLog
from app.services.otp.redis_store import (
    RedisOTPStore,
    redis_otp_store,
    RedisUnavailableError,
)
from app.services.otp.security import (
    store_transient_otp,
    claim_transient_otp,
    is_transient_otp_available,
    verify_user_otp_permission,
)
from app.services.otp.orchestrator import OTPOrchestrator


# -------------------------------------------------------------
# 1 & 2. Production Fail-Closed Architecture (No fakeredis fallback)
# -------------------------------------------------------------
def test_production_mode_fails_closed_without_fakeredis():
    """
    In strict production mode (disable_test_mode()), RedisOTPStore must NEVER
    fall back to fakeredis or process memory. If real Redis is unavailable,
    it must raise RedisUnavailableError.
    """
    # Create store pointing to a non-existent port
    prod_store = RedisOTPStore(redis_url="redis://localhost:59999/0")
    prod_store.disable_test_mode()

    # Must raise RedisUnavailableError
    with pytest.raises(RedisUnavailableError) as exc_info:
        prod_store.store_otp(
            request_id=9901,
            otp_code="123456",
            user_id=1,
            mailbox_id=1,
            account_id=1,
        )
    assert "unreachable" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()

    with pytest.raises(RedisUnavailableError):
        prod_store.claim_otp(request_id=9901, user_id=1)


# -------------------------------------------------------------
# 3. OTP Request Cannot Report Success if Redis Storage Fails
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_orchestrator_fails_request_if_redis_storage_fails(db_session):
    """
    If external email API returns an OTP but Redis transient persistence fails,
    the request must be marked 'failed' (NEVER 'completed').
    """
    acc = EmergentAccount(
        account_identifier="EMG-FAIL-CLOSED-01",
        account_name="Fail Closed Account",
        email="fail-closed@company.internal",
        ownership_type="COMPANY_OWNED",
        status="active",
    )
    db_session.add(acc)
    db_session.commit()

    mb = MailboxAccount(
        email_address="fail-closed@company.internal",
        employee_name="Operator",
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
        correlation_id="cmd_fail_redis_store",
        command_id="8821",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db_session.add(req)
    db_session.commit()

    mock_client = AsyncMock()
    mock_client.retrieve_otp = AsyncMock(return_value={
        "status": "success",
        "message": "OTP Found",
        "data": {"otp": "771122"},
    })

    orchestrator = OTPOrchestrator(
        mail_client=mock_client,
        session_factory=lambda: db_session,
    )

    # Force Redis to fail when storing OTP
    with patch("app.services.otp.orchestrator.store_transient_otp", side_effect=RedisUnavailableError("Redis connection down")):
        with patch("app.services.otp.orchestrator.settings.EMAIL_API_INITIAL_DELAY_SECONDS", 0):
            with patch("app.services.otp.orchestrator.settings.EMAIL_API_RETRY_INTERVAL_SECONDS", 0):
                await orchestrator.execute_polling(req.id)

    req = db_session.query(OTPRequest).filter(OTPRequest.id == req.id).first()
    # MUST be failed, never completed!
    assert req.status == "failed"
    assert "transient storage failure" in req.error_reason.lower()
    assert req.otp_code_hash is None


# -------------------------------------------------------------
# 4. OTP Retrieval Returns HTTP 503 if Redis is Unavailable
# -------------------------------------------------------------
def test_otp_retrieval_returns_503_on_redis_outage(client, admin_token, db_session):
    acc = EmergentAccount(
        account_identifier="EMG-OUTAGE-01",
        account_name="Outage Account",
        email="outage@company.internal",
        ownership_type="COMPANY_OWNED",
        status="active",
    )
    db_session.add(acc)
    db_session.commit()

    mb = MailboxAccount(
        email_address="outage@company.internal",
        employee_name="Operator",
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
        status="completed",
        correlation_id="cmd_redis_503_test",
        command_id="3344",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db_session.add(req)
    db_session.commit()

    with patch("app.services.otp.service.claim_transient_otp", side_effect=RedisUnavailableError("Cluster unreachable")):
        resp = client.get(
            f"/api/v1/otp/{req.id}/result",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "unavailable" in resp.json()["detail"].lower()


# -------------------------------------------------------------
# 5. Redis Reconnect After Outage
# -------------------------------------------------------------
def test_redis_reconnect_after_outage():
    """
    Verifies that store recovers after an outage without application restart.
    """
    store = RedisOTPStore()
    fake = fakeredis.FakeRedis(decode_responses=True)
    store.enable_test_mode(fake)

    # Success 1
    store.store_otp(9902, "111222", user_id=1, mailbox_id=1, account_id=1)
    assert store.claim_otp(9902, user_id=1, mailbox_id=1, account_id=1) == "111222"

    # Outage: mock client pipeline raising ConnectionError
    with patch.object(fake, "pipeline", side_effect=redis.ConnectionError("Connection lost")):
        with pytest.raises(RedisUnavailableError):
            store.store_otp(9903, "333444", user_id=1, mailbox_id=1, account_id=1)

    # Recovery: outage clears
    store.store_otp(9903, "333444", user_id=1, mailbox_id=1, account_id=1)
    assert store.claim_otp(9903, user_id=1, mailbox_id=1, account_id=1) == "333444"


# -------------------------------------------------------------
# 6 & 7. Database Unique Command ID Rejection & Concurrent Safe Handling
# -------------------------------------------------------------
def test_db_unique_command_id_constraint(db_session):
    """
    Verifies that the database raises IntegrityError when duplicate command_ids are inserted.
    """
    mb = MailboxAccount(
        email_address="db-unique@company.internal",
        employee_name="Operator",
        api_base_url="https://m.phx.co.in/automation/api/email-api",
        is_active=True,
    )
    db_session.add(mb)
    db_session.commit()

    req1 = OTPRequest(
        mailbox_id=mb.id,
        correlation_id="cmd_unique_1",
        command_id="CMD_EXACT_DUPLICATE_01",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db_session.add(req1)
    db_session.commit()

    req2 = OTPRequest(
        mailbox_id=mb.id,
        correlation_id="cmd_unique_2",
        command_id="CMD_EXACT_DUPLICATE_01",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db_session.add(req2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_concurrent_duplicate_command_id_api_handling(client, admin_token, db_session):
    """
    Verifies that API catches duplicate commandId insertion and returns HTTP 409 Conflict.
    """
    mb = MailboxAccount(
        email_address="concurrent-dupe@company.internal",
        employee_name="Operator",
        api_base_url="https://m.phx.co.in/automation/api/email-api",
        is_active=True,
        verified_access=True,
    )
    db_session.add(mb)
    db_session.commit()

    # Existing row with command_id 9090 marked as completed so concurrency lock is bypassed
    existing = OTPRequest(
        mailbox_id=mb.id,
        correlation_id="cmd_prior_registered",
        command_id="9090",
        status="completed",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db_session.add(existing)
    db_session.commit()

    mock_dupe = AsyncMock(return_value={
        "status": "success",
        "message": "Command added successfully",
        "data": {"commandId": "9090"},
    })

    with patch("app.services.otp.service.settings.EMAIL_API_ENABLED", True):
        with patch("app.services.otp.mail_api.EmailApiClient.create_email_command", mock_dupe):
            resp = client.post(
                "/api/v1/otp/request",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"mailbox_id": mb.id},
            )
            assert resp.status_code == status.HTTP_409_CONFLICT
            assert "reused or concurrent duplicate" in resp.json()["detail"].lower() or "reused commandid" in resp.json()["detail"].lower()


# -------------------------------------------------------------
# 8 & 9. Unauthorized Claim Does NOT Consume Legitimate OTP
# -------------------------------------------------------------
def test_unauthorized_claim_does_not_consume_legitimate_otp():
    """
    CRITICAL SECURITY INVARIANT:
    An unauthorized user or mismatched binding must NOT delete or consume the legitimate OTP!
    """
    store = RedisOTPStore()
    fake = fakeredis.FakeRedis(decode_responses=True)
    store.enable_test_mode(fake)

    req_id = 9905
    otp = "852963"
    owner_user_id = 10
    attacker_user_id = 99
    mailbox_id = 4
    account_id = 2

    store.store_otp(
        request_id=req_id,
        otp_code=otp,
        user_id=owner_user_id,
        mailbox_id=mailbox_id,
        account_id=account_id,
        ttl_seconds=300,
    )

    # Attacker attempts claim -> rejected
    attacker_attempt = store.claim_otp(
        request_id=req_id,
        user_id=attacker_user_id,
        mailbox_id=mailbox_id,
        account_id=account_id,
        is_admin=False,
    )
    assert attacker_attempt is None
    # KEY MUST STILL EXIST IN REDIS!
    assert store.is_available(req_id) is True

    # Mismatched mailbox attempt -> rejected
    wrong_mb_attempt = store.claim_otp(
        request_id=req_id,
        user_id=owner_user_id,
        mailbox_id=999,
        account_id=account_id,
    )
    assert wrong_mb_attempt is None
    assert store.is_available(req_id) is True

    # Mismatched account attempt -> rejected
    wrong_acc_attempt = store.claim_otp(
        request_id=req_id,
        user_id=owner_user_id,
        mailbox_id=mailbox_id,
        account_id=999,
    )
    assert wrong_acc_attempt is None
    assert store.is_available(req_id) is True

    # Legitimate owner claims -> SUCCEEDS!
    owner_claim = store.claim_otp(
        request_id=req_id,
        user_id=owner_user_id,
        mailbox_id=mailbox_id,
        account_id=account_id,
    )
    assert owner_claim == otp

    # Now it is consumed and deleted
    assert store.is_available(req_id) is False


# -------------------------------------------------------------
# 10. Server-Side Consent: Revocation, Expiry, and Admin Attribution
# -------------------------------------------------------------
def test_consent_admin_attribution_and_expiry(client, admin_token, member_token, db_session):
    admin_user = db_session.query(User).filter(User.email == "admin@emergent-hub.com").first()
    member_user = db_session.query(User).filter(User.email == "member@emergent-hub.com").first()

    # Personal account owned by Admin
    acc = EmergentAccount(
        account_identifier="EMG-ADMIN-CONSENT-01",
        account_name="Founder Account",
        email="founder@company.internal",
        owner_user_id=admin_user.id,
        owner_name="Founder",
        ownership_type="PERSONAL",
        status="active",
    )
    db_session.add(acc)
    db_session.commit()

    perm = AccountPermission(
        user_id=member_user.id,
        account_id=acc.id,
        can_view=True,
        can_execute=True,
    )
    db_session.add(perm)

    mb = MailboxAccount(
        email_address="founder-mb@company.internal",
        employee_name="Assistant",
        account_id=acc.id,
        ownership_type="PERSONAL",
        api_base_url="https://m.phx.co.in/automation/api/email-api",
        is_active=True,
        verified_access=True,
    )
    db_session.add(mb)
    db_session.commit()

    # Admin grants consent on personal account
    grant_resp = client.post(
        f"/api/v1/otp/consents?account_id={acc.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "authorized_member_id": member_user.id,
            "permission_scope": "OTP_RETRIEVAL",
            "expires_in_days": 1,
        },
    )
    assert grant_resp.status_code == status.HTTP_201_CREATED
    data = grant_resp.json()
    assert data["granted_by_user_id"] == admin_user.id

    # Verify audit log recorded admin attribution
    audit_entry = (
        db_session.query(AuditLog)
        .filter(AuditLog.resource_type == "personal_account_consent")
        .order_by(AuditLog.created_at.desc())
        .first()
    )
    assert audit_entry is not None
    assert f"#{admin_user.id}" in audit_entry.details

    # Test expired consent
    consent_record = db_session.query(PersonalAccountConsent).filter(PersonalAccountConsent.id == data["id"]).first()
    # Expire consent back in time
    consent_record.expires_at = datetime.now(timezone.utc) - timedelta(days=2)
    db_session.commit()

    with pytest.raises(ValueError) as exc:
        verify_user_otp_permission(
            user=member_user,
            account=acc,
            mailbox=mb,
            owner_consent_confirmed=True,
            db=db_session,
        )
    assert "expired" in str(exc.value).lower()


# -------------------------------------------------------------
# 11 & 12. Atomic One-Time Claim & Zero Database/Log Storage
# -------------------------------------------------------------
def test_atomic_one_time_claim_and_zero_db_or_log_leakage(client, admin_token, db_session):
    fake = fakeredis.FakeRedis(decode_responses=True)
    redis_otp_store.enable_test_mode(fake)

    try:
        admin_user = db_session.query(User).filter(User.email == "admin@emergent-hub.com").first()
        acc = EmergentAccount(
            account_identifier="EMG-LEAK-TEST-01",
            account_name="Leak Test Account",
            email="leak-test@company.internal",
            ownership_type="COMPANY_OWNED",
            status="active",
        )
        db_session.add(acc)
        db_session.commit()

        mb = MailboxAccount(
            email_address="leak-test@company.internal",
            employee_name="SecTester",
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
            requested_by_user_id=admin_user.id if admin_user else 1,
            status="completed",
            correlation_id="cmd_atomic_and_no_leak",
            command_id="CMD_NO_LEAK_01",
            otp_code_hash=None,  # Zero hash
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        db_session.add(req)
        db_session.commit()

        secret_otp = "741852"

        redis_otp_store.store_otp(
            request_id=req.id,
            otp_code=secret_otp,
            user_id=req.requested_by_user_id,
            mailbox_id=req.mailbox_id,
            account_id=req.account_id,
            ttl_seconds=300,
        )

        # Claim 1: must succeed
        c1 = client.get(
            f"/api/v1/otp/{req.id}/result",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert c1.status_code == status.HTTP_200_OK
        assert c1.json()["otp_code"] == secret_otp

        # Claim 2: must return 410 Gone (atomic one-time claim)
        c2 = client.get(
            f"/api/v1/otp/{req.id}/result",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert c2.status_code == status.HTTP_410_GONE

        # Verify zero database hash storage
        db_session.refresh(req)
        assert req.otp_code_hash is None

        # Verify secret OTP never in audit logs
        audit_logs = db_session.query(AuditLog).all()
        for entry in audit_logs:
            if entry.details:
                assert secret_otp not in entry.details
    finally:
        redis_otp_store.enable_test_mode()
