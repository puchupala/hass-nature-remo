"""Shared fixtures for the Nature Remo tests."""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


@pytest.fixture
def hass_config_dir(tmp_path: Path) -> str:
    """Use a temporary config directory that exposes this repo's integration."""
    (tmp_path / "custom_components").symlink_to(
        REPO_ROOT / "custom_components", target_is_directory=True
    )
    return str(tmp_path)
