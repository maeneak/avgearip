"""Test configuration for AVGear Matrix integration."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest_plugins = ("pytest_homeassistant_custom_component",)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations defined in this repository."""
