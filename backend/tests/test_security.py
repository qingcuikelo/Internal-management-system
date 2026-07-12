
import pytest

from app.core.security import (
    hash_password, verify_password, create_access_token, create_refresh_token, decode_token,
)
from app.core.exceptions import BizError


def test_password_hash_roundtrip():
    h = hash_password("Abc12345")
    assert h != "Abc12345"
    assert verify_password("Abc12345", h)
    assert not verify_password("wrong", h)


def test_access_token_encodes_claims():
    token, jti, expires_in = create_access_token("user-1")
    payload = decode_token(token)
    assert payload["sub"] == "user-1"
    assert payload["type"] == "access"
    assert payload["jti"] == jti
    assert expires_in > 0
    assert "iat" in payload


def test_refresh_token_type():
    token, jti = create_refresh_token("user-1")
    assert decode_token(token)["type"] == "refresh"


def test_decode_invalid_raises():
    with pytest.raises(BizError):
        decode_token("not.a.jwt")
