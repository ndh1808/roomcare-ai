from dataclasses import replace

import pytest

from roomcare.config import Settings, load_settings
from roomcare.security import DEMO_PASSWORD, authenticate, hash_password, verify_password


def test_password_hash_salted_and_verified():
    one = hash_password("example-secure-password")
    two = hash_password("example-secure-password")
    assert one != two
    assert "example-secure-password" not in one
    assert verify_password("example-secure-password", one)
    assert not verify_password("wrong-password", one)
    for invalid in ["", "pbkdf2_sha256$1$abc$def", "unknown$600000$abc$def", None]:
        assert not verify_password("example-secure-password", invalid)
    with pytest.raises(ValueError):
        hash_password("short")


def test_demo_auth_is_explicit_and_custom_hash_overrides_demo():
    demo = Settings(demo_mode=True)
    assert authenticate("chu-tro", DEMO_PASSWORD, demo)
    assert not authenticate("other", DEMO_PASSWORD, demo)
    assert not authenticate("chu-tro", DEMO_PASSWORD, replace(demo, demo_mode=False))
    custom = replace(demo, admin_password_hash=hash_password("a-custom-long-password"))
    assert not authenticate("chu-tro", DEMO_PASSWORD, custom)
    assert authenticate("chu-tro", "a-custom-long-password", custom)


def test_production_fails_closed_without_shared_db_and_hash():
    with pytest.raises(ValueError, match="PostgreSQL"):
        replace(Settings(), demo_mode=False).validate()
    with pytest.raises(ValueError, match="ADMIN_PASSWORD_HASH"):
        replace(Settings(), demo_mode=False, database_url="postgresql://test:test@localhost/test").validate()
    replace(Settings(), demo_mode=False, database_url="postgresql://test:test@localhost/test", admin_password_hash=hash_password("a-custom-long-password")).validate()


def test_malformed_hash_is_rejected_and_secrets_are_not_repr():
    with pytest.raises(ValueError, match="ADMIN_PASSWORD_HASH"):
        replace(Settings(), admin_password_hash="pbkdf2_sha256$broken").validate()
    settings = replace(Settings(), gemini_api_key="secret-api-key", database_url="postgresql://user:secret-db-password@host/db", admin_password_hash="secret-hash")
    assert "secret-api-key" not in repr(settings)
    assert "secret-db-password" not in repr(settings)
    assert "secret-hash" not in repr(settings)


def test_env_settings(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("BUILDING_NAME", "Nhà trọ thử nghiệm")
    result = load_settings()
    assert result.demo_mode
    assert result.building_name == "Nhà trọ thử nghiệm"
    assert result.database_url == "sqlite:///:memory:"
    monkeypatch.setenv("DEMO_MODE", "oops")
    with pytest.raises(ValueError, match="DEMO_MODE"):
        load_settings()
