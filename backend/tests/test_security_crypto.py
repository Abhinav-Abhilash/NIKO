from datetime import timedelta

import pytest
from cryptography.fernet import Fernet

from backend.app.core.exceptions import AuthenticationError
from backend.app.core.security import (
    create_jwt_token,
    decode_jwt_token,
    decrypt_secret,
    encrypt_secret,
    hash_password,
    verify_password,
)


def test_fernet_secret_encryption_roundtrip() -> None:
    key = Fernet.generate_key().decode()
    original_secret = "sk-test-super-secret-api-key-12345"

    encrypted = encrypt_secret(original_secret, key)
    assert encrypted != original_secret

    decrypted = decrypt_secret(encrypted, key)
    assert decrypted == original_secret


def test_fernet_secret_decryption_invalid_key() -> None:
    key1 = Fernet.generate_key().decode()
    key2 = Fernet.generate_key().decode()

    encrypted = encrypt_secret("some_secret", key1)
    with pytest.raises(AuthenticationError):
        decrypt_secret(encrypted, key2)


def test_argon2id_password_hashing() -> None:
    password = "MyComplexPassword#2026!"
    pw_hash = hash_password(password)

    assert pw_hash.startswith("$argon2id$")
    assert verify_password(password, pw_hash) is True
    assert verify_password("WrongPassword", pw_hash) is False


def test_jwt_token_generation_and_validation() -> None:
    secret = "test_jwt_secret_key_abcdef12345678"
    payload = {"sub": "user_123", "role": "owner"}

    token = create_jwt_token(payload, secret_key=secret, expires_delta=timedelta(minutes=5))
    decoded = decode_jwt_token(token, secret_key=secret)

    assert decoded["sub"] == "user_123"
    assert decoded["role"] == "owner"
    assert "exp" in decoded
