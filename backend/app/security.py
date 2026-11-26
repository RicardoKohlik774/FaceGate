"""Security helpers. More (passwords, JWT, encryption) come with later steps."""
import hashlib
import secrets


def new_device_key() -> str:
    """A random secret key for one door camera (43 characters)."""
    return secrets.token_urlsafe(32)


def hash_device_key(key: str) -> str:
    """The SHA-256 hash of a device key; only this is stored in the database.

    A device key is long and random, so a plain SHA-256 is enough: there is
    nothing to guess, unlike a human password, which needs a slow hash.
    """
    return hashlib.sha256(key.encode()).hexdigest()
