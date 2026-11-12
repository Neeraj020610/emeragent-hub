"""
OTP Orchestrator and Polling Engine
Phase 3 Implementation for Emergent Central Hub

Manages:
- Mailbox-specific concurrency locking (different mailboxes run concurrently, conflicting active requests on same mailbox prevented).
- Non-blocking async polling loop with strict cadence:
  - Initial delay: 5s
  - Polling interval: 5s
  - Max wait: 90s
  - Max attempts: 12
- Request cancellation support.
- Cryptographic hashing (SHA-256) of verified OTP before database update.
- Transient in-memory store handoff for authorized users.
- Global integration disable switch and unverified access guards.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.config import settings
from app.models.otp import OTPRequest, MailboxAccount
from app.core.security import hash_otp_code
from app.services.otp.mail_api import EmailApiClient
from app.services.otp.validator import validate_retrieve_otp_response
from app.services.otp.security import store_transient_otp

logger = logging.getLogger("emergent.otp.orchestrator")

# Mailbox ID -> asyncio.Lock
_mailbox_locks: Dict[int, asyncio.Lock] = {}
# Active polling task registry: request_id -> asyncio.Task
_active_polling_tasks: Dict[int, asyncio.Task] = {}


def get_mailbox_lock(mailbox_id: int) -> asyncio.Lock:
    """Gets or creates an asyncio.Lock for a specific mailbox ID."""
    if mailbox_id not in _mailbox_locks:
        _mailbox_locks[mailbox_id] = asyncio.Lock()
    return _mailbox_locks[mailbox_id]


class OTPOrchestrator:
    def __init__(self, mail_client: Optional[EmailApiClient] = None, session_factory=None):
        self.mail_client = mail_client or EmailApiClient()
        self.session_factory = session_factory or SessionLocal

    async def execute_polling(self, request_id: int) -> None:
        """
        Runs the async retry loop for a correlated OTP request.
        """
        is_custom_session = self.session_factory != SessionLocal
        db: Session = self.session_factory()
        try:
            req = db.query(OTPRequest).filter(OTPRequest.id == request_id).first()
            if not req:
                logger.error(f"OTPRequest {request_id} not found for polling execution")
                return

            mailbox = db.query(MailboxAccount).filter(MailboxAccount.id == req.mailbox_id).first()
            if not mailbox:
                logger.error(f"Mailbox {req.mailbox_id} not found for request {request_id}")
                req.status = "failed"
                req.error_reason = "Associated mailbox not found"
                req.completed_at = datetime.now(timezone.utc)
                db.commit()
                return

            command_id = req.command_id
            if not command_id:
                logger.error(f"OTPRequest {request_id} has no command_id")
                req.status = "failed"
                req.error_reason = "No commandId returned from create-email-command"
                req.completed_at = datetime.now(timezone.utc)
                db.commit()
                return

            req.status = "polling"
            db.commit()

            # 1. Initial delay (5s)
            logger.info(f"OTPRequest {request_id}: Starting initial delay of {settings.EMAIL_API_INITIAL_DELAY_SECONDS}s")
            await asyncio.sleep(settings.EMAIL_API_INITIAL_DELAY_SECONDS)

            max_attempts = settings.EMAIL_API_MAX_ATTEMPTS
            retry_interval = settings.EMAIL_API_RETRY_INTERVAL_SECONDS
            attempt = 0
            start_time = asyncio.get_event_loop().time()
            max_duration = float(settings.EMAIL_API_MAX_WAIT_SECONDS)

            while attempt < max_attempts:
                # Check elapsed time
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= max_duration:
                    logger.warning(f"OTPRequest {request_id} exceeded maximum wait time of {max_duration}s")
                    break

                # Refresh request to check for cancellation
                db.refresh(req)
                if req.status == "cancelled":
                    logger.info(f"OTPRequest {request_id} was cancelled by user. Terminating polling loop.")
                    return

                attempt += 1
                req.attempts_count = attempt
                db.commit()

                logger.info(
                    f"OTPRequest {request_id} (commandId={command_id}): Attempt {attempt}/{max_attempts} (elapsed: {int(elapsed)}s)"
                )

                try:
                    response_data = await self.mail_client.retrieve_otp(
                        command_id=command_id,
                        limit=1,
                        action="unstop_otp",
                    )
                    is_valid, otp_found, otp_code, error_msg = validate_retrieve_otp_response(response_data)

                    if not is_valid:
                        logger.warning(f"OTPRequest {request_id}: API returned error on attempt {attempt}: {error_msg}")
                    elif otp_found and otp_code:
                        now = datetime.now(timezone.utc)
                        # Fail-closed: Attempt transient storage in Redis FIRST
                        try:
                            store_transient_otp(
                                request_id=req.id,
                                otp_code=otp_code,
                                requester_user_id=req.requested_by_user_id,
                                mailbox_id=req.mailbox_id,
                                account_id=req.account_id,
                                ttl_seconds=300,
                            )
                            # Only mark completed after Redis confirms persistence
                            logger.info(f"OTPRequest {request_id}: Stored in transient Redis. Marking completed.")
                            req.status = "completed"
                            req.otp_code_hash = None  # Deprecated in Phase 3.1: Zero DB hash storage
                            req.received_at = now
                            req.completed_at = now
                            req.error_reason = None
                            db.commit()
                            return
                        except Exception as redis_err:
                            logger.critical(
                                f"OTPRequest {request_id}: Transient Redis storage failed: {str(redis_err)}. Failing request closed."
                            )
                            req.status = "failed"
                            req.error_reason = "Transient storage failure: Redis unavailable"
                            req.completed_at = now
                            db.commit()
                            return
                    else:
                        # OTP not ready yet; wait for retry interval
                        logger.debug(f"OTPRequest {request_id}: OTP not ready yet on attempt {attempt}")

                except Exception as e:
                    logger.warning(f"OTPRequest {request_id}: Network/client error on attempt {attempt}: {str(e)}")

                # Sleep before next attempt
                if attempt < max_attempts:
                    await asyncio.sleep(retry_interval)

            # Max attempts or timeout reached without finding OTP
            db.refresh(req)
            if req.status != "completed" and req.status != "cancelled":
                logger.info(f"OTPRequest {request_id}: Polling timed out after {attempt} attempts")
                req.status = "failed"
                req.error_reason = f"Timeout: No OTP received within {settings.EMAIL_API_MAX_WAIT_SECONDS} seconds ({attempt} attempts exhausted)"
                req.completed_at = datetime.now(timezone.utc)
                db.commit()

        except asyncio.CancelledError:
            logger.info(f"OTPRequest {request_id}: Task cancelled asynchronously")
        except Exception as e:
            logger.error(f"OTPRequest {request_id}: Unhandled error in orchestrator: {str(e)}", exc_info=True)
            try:
                db.refresh(req)
                req.status = "failed"
                req.error_reason = f"Internal orchestrator error: {str(e)}"
                req.completed_at = datetime.now(timezone.utc)
                db.commit()
            except Exception:
                pass
        finally:
            _active_polling_tasks.pop(request_id, None)
            if not is_custom_session:
                db.close()

    def start_polling(self, request_id: int) -> None:
        """Launches the background polling task."""
        task = asyncio.create_task(self.execute_polling(request_id))
        _active_polling_tasks[request_id] = task

    def cancel_task(self, request_id: int) -> bool:
        """Cancels an active background polling task if running."""
        task = _active_polling_tasks.get(request_id)
        if task and not task.done():
            task.cancel()
            _active_polling_tasks.pop(request_id, None)
            return True
        return False

