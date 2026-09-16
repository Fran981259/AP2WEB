"""Tests for safe first-administrator bootstrap configuration."""
from __future__ import annotations

import pytest

from backend.app import config


def test_bootstrap_admin_settings_must_be_paired():
    with pytest.raises(RuntimeError, match="must be set together"):
        config.Settings({
            "AP2WEB_ENV": "development",
            "AP2WEB_BOOTSTRAP_ADMIN_USERNAME": "firstadmin",
        })


def test_bootstrap_admin_settings_accept_complete_pair():
    settings = config.Settings({
        "AP2WEB_ENV": "development",
        "AP2WEB_BOOTSTRAP_ADMIN_USERNAME": "firstadmin",
        "AP2WEB_BOOTSTRAP_ADMIN_PASSWORD": "strong-bootstrap-password",
    })
    assert settings.bootstrap_admin_username == "firstadmin"
