"""Fixtures for the supported, key-free HTTP workflow."""

import pytest

from app import create_app


@pytest.fixture
def client(monkeypatch):
    # Keep tests offline even when a developer has credentials in their shell.
    monkeypatch.setenv("CLAUDE_API_KEY", "")
    monkeypatch.setenv("PIPELINE_MODE", "manual")
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()
