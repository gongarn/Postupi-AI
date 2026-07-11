import hashlib
import hmac
import unicodedata


def normalize_uid(uid: str) -> str:
    if not isinstance(uid, str):
        raise TypeError("UID must be a string")
    return unicodedata.normalize("NFKC", uid.strip())


def hash_uid(*, secret: str, identity_namespace: str, uid: str) -> str:
    if not identity_namespace.strip():
        raise ValueError("identity_namespace must not be empty")
    normalized = normalize_uid(uid)
    message = f"{identity_namespace}:{normalized}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
