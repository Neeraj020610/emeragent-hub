"""
Redis-Backed Transient OTP Store with Fail-Closed Reliability & Atomic One-Time Retrieval
Phase 3.2 Implementation for Emergent Central Hub

Strict Security & Architectural Rules:
1. FAIL-CLOSED ARCHITECTURE:
   - Mandatory real Redis in production paths.
   - If Redis is unavailable, immediately raises RedisUnavailableError (HTTP 503).
   - Zero fallback to process memory or fake backends in production mode.
   - FakeRedis is restricted strictly and exclusively to isolated automated test harnesses.
2. ATOMIC ONE-TIME RETRIEVAL WITHOUT INADVERTENT CONSUMPTION:
   - Atomic Lua script verifies user_id, mailbox_id, and account_id BEFORE deleting the key.
   - Unauthorized requests or mismatched credentials return error codes without deleting the OTP.
   - Authorized requests atomically fetch and delete the transient record in one operation.
3. ZERO DATABASE PERSISTENCE:
   - Raw OTP codes and hashes are never persisted in PostgreSQL.
   - Kept in Redis only, encrypted with Fernet (AES-128-CBC + HMAC-SHA256) with a 5-minute TTL.
"""
import json
import logging
import time
from typing import Any, Dict, Optional

import redis
from app.config import settings
from app.core.security import encrypt_token, decrypt_token

logger = logging.getLogger("emergent.otp.redis_store")


class RedisUnavailableError(Exception):
    """Raised when the mandatory Redis transient storage service is unreachable."""
    pass


# Atomic Lua script that inspects metadata bindings BEFORE deleting
# Guarantees that unauthorized requests NEVER delete legitimate OTPs
LUA_VERIFY_AND_CLAIM = """
local key = KEYS[1]
local req_user = ARGV[1]
local req_mb = ARGV[2]
local req_acc = ARGV[3]
local is_admin = ARGV[4]

local stored_user = redis.call('HGET', key, 'user_id')
if not stored_user then
    return 'NOT_FOUND'
end

local stored_mb = redis.call('HGET', key, 'mailbox_id')
local stored_acc = redis.call('HGET', key, 'account_id')

-- Check user authorization
if is_admin ~= '1' and stored_user ~= req_user then
    return 'AUTH_MISMATCH'
end

-- Check mailbox binding
if req_mb ~= '' and stored_mb ~= req_mb then
    return 'MAILBOX_MISMATCH'
end

-- Check account binding
if req_acc ~= '' and stored_acc ~= req_acc then
    return 'ACCOUNT_MISMATCH'
end

-- Authorized: Atomically get encrypted payload and delete the key
local payload = redis.call('HGET', key, 'payload')
redis.call('DEL', key)
return payload
"""


class RedisOTPStore:
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self.key_prefix = getattr(settings, "REDIS_KEY_PREFIX", "ech:otp:transient")
        self._client: Optional[redis.Redis] = None
        self._test_mode: bool = False
        self._test_client: Optional[Any] = None
        self._lua_script = None

    def enable_test_mode(self, test_client: Optional[Any] = None) -> None:
        """
        EXCLUSIVELY FOR AUTOMATED UNIT TESTS:
        Configures an isolated in-memory test client to enable test suites
        to run without requiring an external physical Redis cluster.
        """
        import fakeredis
        self._test_mode = True
        self._test_client = test_client or fakeredis.FakeRedis(decode_responses=True)
        self._lua_script = None

    def disable_test_mode(self) -> None:
        """Restores strict production mode requiring live Redis."""
        self._test_mode = False
        self._test_client = None
        self._client = None
        self._lua_script = None

    def get_client(self) -> redis.Redis:
        """
        Returns an active Redis client.
        In production, connects strictly to real Redis and fails closed on connection error.
        """
        if self._test_mode:
            return self._test_client

        if self._client is not None:
            try:
                self._client.ping()
                return self._client
            except (redis.ConnectionError, redis.TimeoutError):
                self._client = None
                self._lua_script = None

        try:
            r = redis.Redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                socket_connect_timeout=settings.REDIS_SOCKET_TIMEOUT,
            )
            r.ping()
            self._client = r
            logger.info(f"Connected to Redis cluster at {self.redis_url}")
            return self._client
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.error(f"Mandatory Redis connection failed for {self.redis_url}: {str(e)}")
            raise RedisUnavailableError(
                "OTP transient storage service (Redis) is currently unreachable. Request rejected fail-closed."
            ) from e

    def _make_key(self, request_id: int) -> str:
        return f"{self.key_prefix}:{request_id}"

    def store_otp(
        self,
        request_id: int,
        otp_code: str,
        user_id: Optional[int],
        mailbox_id: int,
        account_id: Optional[int],
        ttl_seconds: int = 300,
    ) -> bool:
        """
        Stores encrypted OTP and metadata fields in a Redis Hash with TTL.
        Fails closed by raising RedisUnavailableError if Redis is down.
        """
        r = self.get_client()
        key = self._make_key(request_id)
        now = time.time()

        payload = {
            "request_id": request_id,
            "otp": otp_code,
            "created_at": now,
            "expires_at": now + ttl_seconds,
        }

        # Encrypt the sensitive payload
        encrypted_val = encrypt_token(json.dumps(payload))

        # Store in Redis Hash
        mapping = {
            "user_id": str(user_id) if user_id is not None else "",
            "mailbox_id": str(mailbox_id),
            "account_id": str(account_id) if account_id is not None else "",
            "payload": encrypted_val,
        }

        try:
            pipeline = r.pipeline()
            pipeline.hset(name=key, mapping=mapping)
            pipeline.expire(name=key, time=ttl_seconds)
            pipeline.execute()
            logger.info(f"Stored encrypted transient OTP for request_id={request_id} in Redis namespace '{self.key_prefix}' with TTL={ttl_seconds}s")
            return True
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.error(f"Redis write failure for request_id={request_id}: {str(e)}")
            raise RedisUnavailableError("Failed to persist OTP to transient Redis storage.") from e

    def is_available(self, request_id: int) -> bool:
        """Checks if an active, unexpired OTP exists in Redis."""
        try:
            r = self.get_client()
            return bool(r.exists(self._make_key(request_id)))
        except RedisUnavailableError:
            return False
        except Exception:
            return False

    def claim_otp(
        self,
        request_id: int,
        user_id: int,
        mailbox_id: Optional[int] = None,
        account_id: Optional[int] = None,
        is_admin: bool = False,
    ) -> Optional[str]:
        """
        Atomically inspects bindings and claims the OTP.
        If binding mismatches, the key is NOT deleted, preventing unauthorized consumption.
        Fails closed on Redis outage.
        """
        r = self.get_client()
        key = self._make_key(request_id)

        try:
            if not self._lua_script:
                self._lua_script = r.register_script(LUA_VERIFY_AND_CLAIM)

            res = self._lua_script(
                keys=[key],
                args=[
                    str(user_id),
                    str(mailbox_id) if mailbox_id is not None else "",
                    str(account_id) if account_id is not None else "",
                    "1" if is_admin else "0",
                ],
            )
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.error(f"Redis read failure during OTP claim for request_id={request_id}: {str(e)}")
            raise RedisUnavailableError("Failed to query Redis transient storage.") from e

        if not res or res == "NOT_FOUND":
            logger.info(f"OTP claim failed for request_id={request_id}: Key does not exist or already claimed")
            return None

        if res == "AUTH_MISMATCH":
            logger.warning(
                f"Security Alert: Unauthorized user {user_id} attempted to claim OTP for request_id={request_id}. "
                "OTP was NOT consumed or deleted."
            )
            return None

        if res == "MAILBOX_MISMATCH":
            logger.warning(
                f"Security Alert: Mailbox mismatch ({mailbox_id}) on OTP claim for request_id={request_id}. "
                "OTP was NOT consumed or deleted."
            )
            return None

        if res == "ACCOUNT_MISMATCH":
            logger.warning(
                f"Security Alert: Account mismatch ({account_id}) on OTP claim for request_id={request_id}. "
                "OTP was NOT consumed or deleted."
            )
            return None

        # res is the encrypted payload string; key has been atomically deleted
        try:
            json_str = decrypt_token(str(res))
            data = json.loads(json_str)
            otp = data.get("otp")
            logger.info(f"Successfully claimed and zeroized transient OTP for request_id={request_id}")
            return otp
        except Exception as e:
            logger.error(f"Failed to decrypt claimed OTP payload for request_id={request_id}: {str(e)}")
            return None

    def clear(self, request_id: int) -> None:
        """Deletes OTP from Redis."""
        try:
            r = self.get_client()
            r.delete(self._make_key(request_id))
        except Exception:
            pass


# Global singleton instance
redis_otp_store = RedisOTPStore()
