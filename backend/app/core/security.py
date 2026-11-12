import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union
import bcrypt
from cryptography.fernet import Fernet
from jose import jwt
from app.config import settings

# Derive a deterministic, urlsafe 32-byte key from settings.SECRET_KEY for AES token encryption
_fernet_key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
_cipher = Fernet(_fernet_key)


def hash_password(password: str) -> str:
    """Hash a password securely using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def hash_otp_code(otp_code: str) -> str:
    """Hash OTP value with SHA-256 so raw OTP is never stored in plaintext."""
    return hashlib.sha256(otp_code.encode("utf-8")).hexdigest()


def verify_otp_code(plain_otp: str, hashed_otp: str) -> bool:
    """Verify raw OTP against stored SHA-256 hash."""
    return hashlib.sha256(plain_otp.encode("utf-8")).hexdigest() == hashed_otp


def encrypt_token(plain_token: str) -> str:
    """Encrypt an OAuth access or refresh token using Fernet (AES-128-CBC + HMAC-SHA256)."""
    if not plain_token:
        return ""
    return _cipher.encrypt(plain_token.encode("utf-8")).decode("utf-8")


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt an encrypted OAuth token."""
    if not encrypted_token:
        return ""
    try:
        return _cipher.decrypt(encrypted_token.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except Exception:
        return None
