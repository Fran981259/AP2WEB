"""Phase 2 security tests — production config validation (no DB needed)."""
import pytest

from backend.app import config


def test_production_rejects_short_secret():
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        config.Settings({
            "AP2WEB_ENV": "production",
            "AP2WEB_SECRET": "short",
            "AP2WEB_ORIGINS": "https://ok.example.com",
            "AP2WEB_ENFORCE_ROLES": "true",
            "AP2WEB_COOKIE_SECURE": "true",
        })


def test_production_rejects_placeholder_secret():
    with pytest.raises(RuntimeError, match="placeholder"):
        config.Settings({
            "AP2WEB_ENV": "production",
            "AP2WEB_SECRET": "dev-secret-change-me-please-use-env-var-0123456789abcdef",
            "AP2WEB_ORIGINS": "https://ok.example.com",
            "AP2WEB_ENFORCE_ROLES": "true",
            "AP2WEB_COOKIE_SECURE": "true",
        })


def test_production_rejects_enforce_false():
    with pytest.raises(RuntimeError, match="AP2WEB_ENFORCE_ROLES=false"):
        config.Settings({
            "AP2WEB_ENV": "production",
            "AP2WEB_SECRET": "ci-test-secret-do-not-use-in-production-0123456789abcdef",
            "AP2WEB_ORIGINS": "https://ok.example.com",
            "AP2WEB_ENFORCE_ROLES": "false",
            "AP2WEB_COOKIE_SECURE": "true",
        })


def test_production_rejects_cookie_secure_false():
    with pytest.raises(RuntimeError, match="AP2WEB_COOKIE_SECURE=false"):
        config.Settings({
            "AP2WEB_ENV": "production",
            "AP2WEB_SECRET": "ci-test-secret-do-not-use-in-production-0123456789abcdef",
            "AP2WEB_ORIGINS": "https://ok.example.com",
            "AP2WEB_ENFORCE_ROLES": "true",
            "AP2WEB_COOKIE_SECURE": "false",
        })


def test_production_rejects_empty_origins():
    with pytest.raises(RuntimeError, match="explicit origins"):
        config.Settings({
            "AP2WEB_ENV": "production",
            "AP2WEB_SECRET": "ci-test-secret-do-not-use-in-production-0123456789abcdef",
            "AP2WEB_ORIGINS": "",
            "AP2WEB_ENFORCE_ROLES": "true",
            "AP2WEB_COOKIE_SECURE": "true",
        })


def test_production_rejects_wildcard_origin():
    with pytest.raises(RuntimeError, match="Wildcard"):
        config.Settings({
            "AP2WEB_ENV": "production",
            "AP2WEB_SECRET": "ci-test-secret-do-not-use-in-production-0123456789abcdef",
            "AP2WEB_ORIGINS": "https://*.example.com",
            "AP2WEB_ENFORCE_ROLES": "true",
            "AP2WEB_COOKIE_SECURE": "true",
        })


def test_production_accepts_valid_config():
    s = config.Settings({
        "AP2WEB_ENV": "production",
        "AP2WEB_SECRET": "ci-test-secret-do-not-use-in-production-0123456789abcdef",
        "AP2WEB_ORIGINS": "https://ok.example.com",
        "AP2WEB_ENFORCE_ROLES": "true",
        "AP2WEB_COOKIE_SECURE": "true",
        "AP2WEB_RATE_LIMIT_STORAGE": "redis",
        "AP2WEB_REDIS_URL": "redis://localhost:6379/0",
        "DATABASE_URL": "postgresql://user:password@localhost:5432/ap2web",
    })
    assert s.production is True
    assert s.access_token_ttl_seconds > 0
    assert s.refresh_token_ttl_seconds > 0


def test_production_rejects_missing_postgres_url():
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        config.Settings({
            "AP2WEB_ENV": "production",
            "AP2WEB_SECRET": "ci-test-secret-do-not-use-in-production-0123456789abcdef",
            "AP2WEB_ORIGINS": "https://ok.example.com",
            "AP2WEB_ENFORCE_ROLES": "true",
            "AP2WEB_COOKIE_SECURE": "true",
            "AP2WEB_RATE_LIMIT_STORAGE": "redis",
            "AP2WEB_REDIS_URL": "redis://localhost:6379/0",
        })


def test_settings_reads_secret_file(tmp_path):
    secret_path = tmp_path / "ap2web_secret"
    secret_path.write_text("file-backed-secret-value-at-least-32-characters", encoding="utf-8")
    settings = config.Settings({
        "AP2WEB_ENV": "development",
        "AP2WEB_SECRET_FILE": str(secret_path),
    })
    assert settings.secret == "file-backed-secret-value-at-least-32-characters"


def test_production_accepts_database_url_file(tmp_path):
    url_path = tmp_path / "database_url"
    url_path.write_text("postgresql://user:password@localhost:5432/ap2web", encoding="utf-8")
    settings = config.Settings({
        "AP2WEB_ENV": "production",
        "AP2WEB_SECRET": "ci-test-secret-do-not-use-in-production-0123456789abcdef",
        "AP2WEB_ORIGINS": "https://ok.example.com",
        "AP2WEB_ENFORCE_ROLES": "true",
        "AP2WEB_COOKIE_SECURE": "true",
        "AP2WEB_RATE_LIMIT_STORAGE": "redis",
        "AP2WEB_REDIS_URL": "redis://localhost:6379/0",
        "DATABASE_URL_FILE": str(url_path),
    })
    assert settings.database_url == "postgresql://user:password@localhost:5432/ap2web"


def test_production_rejects_memory_ratelimit():
    import pytest

    with pytest.raises(RuntimeError):
        config.Settings({
            "AP2WEB_ENV": "production",
            "AP2WEB_SECRET": "ci-test-secret-do-not-use-in-production-0123456789abcdef",
            "AP2WEB_ORIGINS": "https://ok.example.com",
            "AP2WEB_RATE_LIMIT_STORAGE": "memory",
        })


def test_production_rejects_redis_without_url():
    import pytest

    with pytest.raises(RuntimeError):
        config.Settings({
            "AP2WEB_ENV": "production",
            "AP2WEB_SECRET": "ci-test-secret-do-not-use-in-production-0123456789abcdef",
            "AP2WEB_ORIGINS": "https://ok.example.com",
            "AP2WEB_RATE_LIMIT_STORAGE": "redis",
        })
