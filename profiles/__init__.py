"""
Profile system for SuperClaude framework integration.

This module manages configuration profiles for specialized workflows
including acceptance testing, validation, and deployment automation.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class ProfileLoader:
    """Load and validate SuperClaude profile configurations."""

    def __init__(self, profiles_dir: Path | None = None):
        if profiles_dir is None:
            profiles_dir = Path(__file__).parent
        self.profiles_dir = profiles_dir

    def load_profile(self, profile_name: str) -> dict[str, Any]:
        """Load a profile configuration by name."""
        profile_path = self.profiles_dir / f"{profile_name}.yaml"

        if not profile_path.exists():
            raise FileNotFoundError(f"Profile not found: {profile_path}")

        with open(profile_path) as f:
            config = yaml.safe_load(f)

        return self._validate_profile(config, profile_name)

    def _validate_profile(self, config: dict[str, Any], profile_name: str) -> dict[str, Any]:
        """Validate profile configuration structure."""
        required_fields = ["name", "description", "command", "workflow"]

        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required field '{field}' in profile: {profile_name}")

        return config

    def list_profiles(self) -> list[str]:
        """List available profile names."""
        profiles = []
        for file_path in self.profiles_dir.glob("*.yaml"):
            if file_path.name != "__init__.py":
                profiles.append(file_path.stem)
        return sorted(profiles)
