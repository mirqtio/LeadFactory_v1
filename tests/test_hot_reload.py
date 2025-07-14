"""Tests for hot reload functionality."""
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from d5_scoring.engine import ConfigurableScoringEngine
from d5_scoring.hot_reload import (
    ScoringRulesFileHandler,
    ScoringRulesWatcher,
    get_watcher,
    start_watching,
    stop_watching,
)

# Mark entire module as xfail for Phase 0.5
pytestmark = pytest.mark.xfail(reason="Phase 0.5 feature", strict=False)


class TestScoringRulesFileHandler:
    """Test the file handler for scoring rules changes."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock scoring engine."""
        engine = Mock(spec=ConfigurableScoringEngine)
        engine.rules_parser = Mock()
        engine.rules_parser.rules_file = "config/scoring_rules.yaml"
        engine.reload_rules = Mock()
        return engine

    def test_init(self, mock_engine):
        """Test handler initialization."""
        handler = ScoringRulesFileHandler(mock_engine, debounce_seconds=1.0)

        assert handler.engine == mock_engine
        assert handler.debounce_seconds == 1.0
        assert handler._reload_timer is None

    def test_on_modified_yaml_file(self, mock_engine):
        """Test handling of YAML file modification."""
        handler = ScoringRulesFileHandler(mock_engine, debounce_seconds=0.1)

        # Mock file event
        event = Mock()
        event.src_path = "config/scoring_rules.yaml"

        # Trigger modification
        handler.on_modified(event)

        # Wait for debounce
        time.sleep(0.2)

        # Should have attempted reload
        mock_engine.reload_rules.assert_called_once()

    def test_on_modified_non_yaml_file(self, mock_engine):
        """Test that non-YAML files are ignored."""
        handler = ScoringRulesFileHandler(mock_engine, debounce_seconds=0.1)

        # Mock file event for non-YAML file
        event = Mock()
        event.src_path = "config/something.txt"

        # Trigger modification
        handler.on_modified(event)

        # Wait for potential debounce
        time.sleep(0.2)

        # Should not have attempted reload
        mock_engine.reload_rules.assert_not_called()

    def test_debounce_multiple_changes(self, mock_engine):
        """Test that multiple rapid changes are debounced."""
        handler = ScoringRulesFileHandler(mock_engine, debounce_seconds=0.3)

        # Mock file event
        event = Mock()
        event.src_path = "config/scoring_rules.yaml"

        # Trigger multiple modifications rapidly
        for _ in range(5):
            handler.on_modified(event)
            time.sleep(0.05)  # Less than debounce time

        # Wait for debounce to complete
        time.sleep(0.4)

        # Should only reload once despite multiple events
        assert mock_engine.reload_rules.call_count == 1

    @patch("d5_scoring.hot_reload.validate_rules")
    def test_reload_with_validation_error(self, mock_validate, mock_engine):
        """Test reload fails gracefully with validation error."""
        # Make validation fail
        mock_validate.side_effect = ValueError("Invalid YAML")

        handler = ScoringRulesFileHandler(mock_engine, debounce_seconds=0.1)

        # Trigger reload directly
        handler._perform_reload()

        # Should not have called engine reload
        mock_engine.reload_rules.assert_not_called()

    @patch("d5_scoring.hot_reload.validate_rules")
    @patch("d5_scoring.hot_reload.reload_attempts")
    def test_metrics_on_success(self, mock_metric, mock_validate, mock_engine):
        """Test metrics are recorded on successful reload."""
        mock_validate.return_value = Mock()  # Valid schema

        handler = ScoringRulesFileHandler(mock_engine)
        handler._perform_reload()

        # Check success metric
        mock_metric.labels.assert_called_with(status="success")
        mock_metric.labels().inc.assert_called_once()

    @patch("d5_scoring.hot_reload.validate_rules")
    @patch("d5_scoring.hot_reload.reload_attempts")
    def test_metrics_on_failure(self, mock_metric, mock_validate, mock_engine):
        """Test metrics are recorded on failed reload."""
        mock_engine.reload_rules.side_effect = Exception("Reload failed")

        handler = ScoringRulesFileHandler(mock_engine)
        handler._perform_reload()

        # Check failure metric
        mock_metric.labels.assert_called_with(status="failure")
        mock_metric.labels().inc.assert_called_once()


class TestScoringRulesWatcher:
    """Test the file watcher for scoring rules."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock scoring engine."""
        engine = Mock(spec=ConfigurableScoringEngine)
        engine.rules_parser = Mock()
        engine.rules_parser.rules_file = "config/scoring_rules.yaml"
        return engine

    def test_init(self, mock_engine):
        """Test watcher initialization."""
        watcher = ScoringRulesWatcher(mock_engine)

        assert watcher.engine == mock_engine
        assert watcher.config_path == Path("config/scoring_rules.yaml")
        assert watcher.debounce_seconds == 2.0
        assert not watcher._started

    def test_start_stop(self, mock_engine):
        """Test starting and stopping the watcher."""
        with patch("d5_scoring.hot_reload.Observer") as MockObserver:
            mock_observer = MockObserver.return_value

            watcher = ScoringRulesWatcher(mock_engine)

            # Start watching
            watcher.start()
            assert watcher._started
            mock_observer.start.assert_called_once()

            # Stop watching
            watcher.stop()
            assert not watcher._started
            mock_observer.stop.assert_called_once()
            mock_observer.join.assert_called_once()

    def test_context_manager(self, mock_engine):
        """Test watcher as context manager."""
        with patch("d5_scoring.hot_reload.Observer"):
            watcher = ScoringRulesWatcher(mock_engine)

            with patch.object(watcher, "start") as mock_start:
                with patch.object(watcher, "stop") as mock_stop:
                    with watcher as w:
                        assert w is watcher
                        mock_start.assert_called_once()

                    mock_stop.assert_called_once()

    def test_double_start(self, mock_engine):
        """Test that double start is handled gracefully."""
        with patch("d5_scoring.hot_reload.Observer"):
            watcher = ScoringRulesWatcher(mock_engine)

            watcher.start()
            watcher.start()  # Should not raise

            assert watcher._started

    def test_custom_config_path(self, mock_engine):
        """Test watcher with custom config path."""
        custom_path = "/custom/path/rules.yaml"
        watcher = ScoringRulesWatcher(mock_engine, config_path=custom_path)

        assert watcher.config_path == Path(custom_path)


class TestWatcherSingleton:
    """Test the singleton watcher functionality."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock scoring engine."""
        engine = Mock(spec=ConfigurableScoringEngine)
        engine.rules_parser = Mock()
        engine.rules_parser.rules_file = "config/scoring_rules.yaml"
        return engine

    def test_get_watcher_singleton(self, mock_engine):
        """Test that get_watcher returns singleton instance."""
        # Clear any existing instance
        import d5_scoring.hot_reload

        d5_scoring.hot_reload._watcher_instance = None

        # Get watcher twice
        watcher1 = get_watcher(mock_engine)
        watcher2 = get_watcher(mock_engine)

        # Should be same instance
        assert watcher1 is watcher2

    def test_start_stop_watching(self, mock_engine):
        """Test convenience functions for starting/stopping."""
        # Clear any existing instance
        import d5_scoring.hot_reload

        d5_scoring.hot_reload._watcher_instance = None

        with patch("d5_scoring.hot_reload.Observer"):
            # Start watching
            start_watching(mock_engine)

            # Verify instance created and started
            assert d5_scoring.hot_reload._watcher_instance is not None
            assert d5_scoring.hot_reload._watcher_instance._started

            # Stop watching
            stop_watching()

            # Verify instance cleared
            assert d5_scoring.hot_reload._watcher_instance is None


class TestIntegration:
    """Integration tests with real file system."""

    @pytest.fixture
    def temp_config(self):
        """Create a temporary config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(
                """
version: "1.0"
tiers:
  A: {min: 80, label: "A"}
  B: {min: 60, label: "B"}
  C: {min: 40, label: "C"}
  D: {min: 0, label: "D"}
components:
  test_component:
    weight: 1.0
    factors:
      test_factor: {weight: 1.0}
"""
            )
            temp_path = f.name

        yield temp_path

        # Cleanup
        Path(temp_path).unlink(missing_ok=True)

    def test_real_file_modification(self, temp_config):
        """Test with real file modification."""
        # Create mock engine
        engine = Mock(spec=ConfigurableScoringEngine)
        engine.rules_parser = Mock()
        engine.rules_parser.rules_file = temp_config
        engine.reload_rules = Mock()

        # Create watcher with short debounce
        watcher = ScoringRulesWatcher(engine, debounce_seconds=0.5)

        with watcher:
            # Modify the file
            with open(temp_config, "a") as f:
                f.write("\n# Modified\n")

            # Wait for detection and debounce
            time.sleep(1.0)

        # Should have triggered reload
        engine.reload_rules.assert_called()
