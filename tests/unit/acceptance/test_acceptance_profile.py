"""
Unit tests for acceptance profile configuration.

Tests profile loading, validation, and configuration structure
for PRP-1060 acceptance testing and deployment automation.
"""

from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
import yaml

from profiles import ProfileLoader


class TestProfileLoader:
    """Test ProfileLoader functionality."""

    @pytest.fixture
    def profile_loader(self):
        """Create ProfileLoader instance for testing."""
        return ProfileLoader()

    @pytest.fixture
    def mock_acceptance_config(self):
        """Mock acceptance profile configuration."""
        return {
            "name": "acceptance",
            "description": "Test acceptance profile",
            "command": "/acceptance",
            "workflow": {
                "type": "containerized",
                "steps": [
                    {"name": "setup", "actions": ["clone_repository"]},
                    {"name": "test", "actions": ["run_tests"]},
                ],
            },
            "environment": {"variables": ["REDIS_URL"], "required_secrets": ["VPS_SSH_KEY"]},
        }

    def test_profile_loader_initialization(self, profile_loader):
        """Test ProfileLoader initialization."""
        assert profile_loader.profiles_dir == Path(__file__).parent.parent.parent.parent / "profiles"
        assert isinstance(profile_loader, ProfileLoader)

    def test_profile_loader_custom_directory(self):
        """Test ProfileLoader with custom directory."""
        custom_dir = Path("/custom/profiles")
        loader = ProfileLoader(custom_dir)
        assert loader.profiles_dir == custom_dir

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    @patch("pathlib.Path.exists")
    def test_load_profile_success(self, mock_exists, mock_yaml_load, mock_file, profile_loader, mock_acceptance_config):
        """Test successful profile loading."""
        mock_exists.return_value = True
        mock_yaml_load.return_value = mock_acceptance_config

        result = profile_loader.load_profile("acceptance")

        assert result == mock_acceptance_config
        mock_file.assert_called_once()
        mock_yaml_load.assert_called_once()

    @patch("pathlib.Path.exists")
    def test_load_profile_not_found(self, mock_exists, profile_loader):
        """Test profile loading when file doesn't exist."""
        mock_exists.return_value = False

        with pytest.raises(FileNotFoundError, match="Profile not found"):
            profile_loader.load_profile("nonexistent")

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    @patch("pathlib.Path.exists")
    def test_load_profile_missing_required_field(self, mock_exists, mock_yaml_load, mock_file, profile_loader):
        """Test profile loading with missing required fields."""
        mock_exists.return_value = True
        # Missing 'workflow' field
        incomplete_config = {"name": "test", "description": "Test profile", "command": "/test"}
        mock_yaml_load.return_value = incomplete_config

        with pytest.raises(ValueError, match="Missing required field 'workflow'"):
            profile_loader.load_profile("incomplete")

    def test_validate_profile_success(self, profile_loader, mock_acceptance_config):
        """Test successful profile validation."""
        result = profile_loader._validate_profile(mock_acceptance_config, "acceptance")
        assert result == mock_acceptance_config

    def test_validate_profile_missing_name(self, profile_loader):
        """Test profile validation with missing name field."""
        config = {"description": "Test profile", "command": "/test", "workflow": {"type": "simple"}}

        with pytest.raises(ValueError, match="Missing required field 'name'"):
            profile_loader._validate_profile(config, "test")

    def test_validate_profile_missing_description(self, profile_loader):
        """Test profile validation with missing description field."""
        config = {"name": "test", "command": "/test", "workflow": {"type": "simple"}}

        with pytest.raises(ValueError, match="Missing required field 'description'"):
            profile_loader._validate_profile(config, "test")

    def test_validate_profile_missing_command(self, profile_loader):
        """Test profile validation with missing command field."""
        config = {"name": "test", "description": "Test profile", "workflow": {"type": "simple"}}

        with pytest.raises(ValueError, match="Missing required field 'command'"):
            profile_loader._validate_profile(config, "test")

    def test_validate_profile_missing_workflow(self, profile_loader):
        """Test profile validation with missing workflow field."""
        config = {"name": "test", "description": "Test profile", "command": "/test"}

        with pytest.raises(ValueError, match="Missing required field 'workflow'"):
            profile_loader._validate_profile(config, "test")

    @patch("pathlib.Path.glob")
    def test_list_profiles(self, mock_glob, profile_loader):
        """Test listing available profiles."""
        # Mock profile files
        mock_files = [Path("acceptance.yaml"), Path("validation.yaml"), Path("deployment.yaml")]
        mock_glob.return_value = mock_files

        profiles = profile_loader.list_profiles()

        assert profiles == ["acceptance", "deployment", "validation"]
        mock_glob.assert_called_once_with("*.yaml")

    @patch("pathlib.Path.glob")
    def test_list_profiles_empty(self, mock_glob, profile_loader):
        """Test listing profiles when none exist."""
        mock_glob.return_value = []

        profiles = profile_loader.list_profiles()

        assert profiles == []


class TestAcceptanceProfileConfiguration:
    """Test actual acceptance profile configuration."""

    @pytest.fixture
    def acceptance_profile_path(self):
        """Path to acceptance profile configuration."""
        return Path(__file__).parent.parent.parent.parent / "profiles" / "acceptance.yaml"

    def test_acceptance_profile_exists(self, acceptance_profile_path):
        """Test that acceptance profile file exists."""
        assert acceptance_profile_path.exists(), f"Acceptance profile not found at {acceptance_profile_path}"

    def test_acceptance_profile_valid_yaml(self, acceptance_profile_path):
        """Test that acceptance profile is valid YAML."""
        with open(acceptance_profile_path) as f:
            config = yaml.safe_load(f)

        assert isinstance(config, dict), "Profile configuration must be a dictionary"

    def test_acceptance_profile_required_fields(self, acceptance_profile_path):
        """Test that acceptance profile has all required fields."""
        with open(acceptance_profile_path) as f:
            config = yaml.safe_load(f)

        required_fields = ["name", "description", "command", "workflow"]

        for field in required_fields:
            assert field in config, f"Missing required field: {field}"

    def test_acceptance_profile_name(self, acceptance_profile_path):
        """Test acceptance profile name field."""
        with open(acceptance_profile_path) as f:
            config = yaml.safe_load(f)

        assert config["name"] == "acceptance"
        assert isinstance(config["description"], str)
        assert len(config["description"]) > 0

    def test_acceptance_profile_command(self, acceptance_profile_path):
        """Test acceptance profile command field."""
        with open(acceptance_profile_path) as f:
            config = yaml.safe_load(f)

        assert config["command"] == "/acceptance"

    def test_acceptance_profile_workflow(self, acceptance_profile_path):
        """Test acceptance profile workflow configuration."""
        with open(acceptance_profile_path) as f:
            config = yaml.safe_load(f)

        workflow = config["workflow"]

        assert "type" in workflow
        assert workflow["type"] == "containerized"
        assert "steps" in workflow
        assert isinstance(workflow["steps"], list)
        assert len(workflow["steps"]) > 0

    def test_acceptance_profile_workflow_steps(self, acceptance_profile_path):
        """Test acceptance profile workflow steps."""
        with open(acceptance_profile_path) as f:
            config = yaml.safe_load(f)

        steps = config["workflow"]["steps"]

        # Check that required steps exist
        step_names = [step["name"] for step in steps]
        required_steps = ["setup", "test_execution", "evidence_validation"]

        for required_step in required_steps:
            assert required_step in step_names, f"Missing required workflow step: {required_step}"

    def test_acceptance_profile_environment(self, acceptance_profile_path):
        """Test acceptance profile environment configuration."""
        with open(acceptance_profile_path) as f:
            config = yaml.safe_load(f)

        if "environment" in config:
            env = config["environment"]

            if "variables" in env:
                assert isinstance(env["variables"], list)

            if "required_secrets" in env:
                assert isinstance(env["required_secrets"], list)

    def test_acceptance_profile_evidence(self, acceptance_profile_path):
        """Test acceptance profile evidence configuration."""
        with open(acceptance_profile_path) as f:
            config = yaml.safe_load(f)

        if "evidence" in config:
            evidence = config["evidence"]

            if "redis_keys" in evidence:
                redis_keys = evidence["redis_keys"]
                assert "acceptance_passed" in redis_keys
                assert "deploy_ok" in redis_keys

    def test_acceptance_profile_container(self, acceptance_profile_path):
        """Test acceptance profile container configuration."""
        with open(acceptance_profile_path) as f:
            config = yaml.safe_load(f)

        if "container" in config:
            container = config["container"]

            if "registry" in container:
                assert container["registry"] == "ghcr.io/leadfactory"

    def test_acceptance_profile_deployment(self, acceptance_profile_path):
        """Test acceptance profile deployment configuration."""
        with open(acceptance_profile_path) as f:
            config = yaml.safe_load(f)

        if "deployment" in config:
            deployment = config["deployment"]

            assert "target_host" in deployment
            assert "user" in deployment
            assert "key_path" in deployment

    def test_acceptance_profile_error_handling(self, acceptance_profile_path):
        """Test acceptance profile error handling configuration."""
        with open(acceptance_profile_path) as f:
            config = yaml.safe_load(f)

        if "error_handling" in config:
            error_handling = config["error_handling"]

            if "rollback_triggers" in error_handling:
                assert isinstance(error_handling["rollback_triggers"], list)

            if "rollback_actions" in error_handling:
                assert isinstance(error_handling["rollback_actions"], list)

    def test_acceptance_profile_promotion_integration(self, acceptance_profile_path):
        """Test acceptance profile integration with PRP-1059 promotion system."""
        with open(acceptance_profile_path) as f:
            config = yaml.safe_load(f)

        if "promotion" in config:
            promotion = config["promotion"]

            assert "lua_script" in promotion
            assert promotion["lua_script"] == "redis/promote.lua"

            if "evidence_requirements" in promotion:
                requirements = promotion["evidence_requirements"]
                assert isinstance(requirements, list)

                # Check for required evidence keys
                evidence_keys = [req["key"] for req in requirements]
                assert "acceptance_passed" in evidence_keys
                assert "deploy_ok" in evidence_keys

    def test_acceptance_profile_monitoring(self, acceptance_profile_path):
        """Test acceptance profile monitoring configuration."""
        with open(acceptance_profile_path) as f:
            config = yaml.safe_load(f)

        if "monitoring" in config:
            monitoring = config["monitoring"]

            if "metrics" in monitoring:
                assert isinstance(monitoring["metrics"], list)

            if "alerts" in monitoring:
                assert isinstance(monitoring["alerts"], list)

    def test_acceptance_profile_security(self, acceptance_profile_path):
        """Test acceptance profile security configuration."""
        with open(acceptance_profile_path) as f:
            config = yaml.safe_load(f)

        if "security" in config:
            security = config["security"]

            # Check security features are enabled
            if "ssh_key_rotation" in security:
                assert isinstance(security["ssh_key_rotation"], bool)

            if "container_security_scanning" in security:
                assert isinstance(security["container_security_scanning"], bool)

    def test_acceptance_profile_testing_config(self, acceptance_profile_path):
        """Test acceptance profile testing configuration."""
        with open(acceptance_profile_path) as f:
            config = yaml.safe_load(f)

        if "testing" in config:
            testing = config["testing"]

            if "coverage_requirements" in testing:
                coverage = testing["coverage_requirements"]
                assert "minimum_percentage" in coverage
                assert isinstance(coverage["minimum_percentage"], int)
                assert coverage["minimum_percentage"] >= 80
