"""Pytest configuration and fixtures for satellite collector tests."""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: tests that require real API access (deselect with '-m \"not integration\"')",
    )
