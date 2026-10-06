import hashlib
import secrets

from pwdlib import PasswordHash

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash(secrets.token_urlsafe(32))


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def verify_password(value: str, hashed: str) -> bool:
    try:
        return passwords.verify(value, hashed)
    except ValueError:
        return False
