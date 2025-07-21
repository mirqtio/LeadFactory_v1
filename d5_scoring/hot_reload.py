"""
Hot reload mechanism for scoring rules configuration.

This module provides file watching and automatic reloading of scoring
rules when the YAML configuration changes.
"""

import threading
import time
from pathlib import Path

from watchdog.events import FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from core.logging import get_logger
from core.metrics import metrics

from .engine import ConfigurableScoringEngine
from .rules_schema import validate_rules

logger = get_logger(__name__)


class ScoringRulesFileHandler(FileSystemEventHandler):
    """Handles file system events for scoring rules YAML."""

    def __init__(self, engine: ConfigurableScoringEngine, debounce_seconds: float = 2.0):
        """
        Initialize file handler.

        Args:
            engine: Scoring engine to reload
            debounce_seconds: Time to wait before reloading after change
        """
        self.engine = engine
        self.debounce_seconds = debounce_seconds
        self._reload_timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def on_modified(self, event):
        """Handle file modification event."""
        if isinstance(event, FileModifiedEvent) and event.src_path.endswith(".yaml"):
            logger.info(f"Detected change in {event.src_path}")
            self._schedule_reload()

    def _schedule_reload(self):
        """Schedule a reload after debounce period."""
        with self._lock:
            # Cancel existing timer if any
            if self._reload_timer and self._reload_timer.is_alive():
                self._reload_timer.cancel()

            # Schedule new reload
            self._reload_timer = threading.Timer(self.debounce_seconds, self._perform_reload)
            self._reload_timer.daemon = True
            self._reload_timer.start()

    def _perform_reload(self):
        """Perform the actual reload."""
        start_time = time.time()

        try:
            logger.info("Reloading scoring rules...")

            # First validate the new configuration
            config_path = self.engine.rules_parser.rules_file
            validate_rules(config_path)

            # If validation passes, reload
            self.engine.reload_rules()

            # Track success metrics
            duration = time.time() - start_time
            metrics.track_config_reload("scoring_rules", duration, status="success")

            logger.info("Scoring rules reloaded successfully")

        except Exception as e:
            # Track failure metrics
            duration = time.time() - start_time
            metrics.track_config_reload("scoring_rules", duration, status="failure")

            logger.error(
                f"Failed to reload scoring rules: {e}",
                extra={
                    "event": "rules_reload",
                    "status": "failure",
                    "msg": str(e),
                    "sha": self._get_git_sha(),
                    "timestamp": time.time(),
                },
            )

    def _get_git_sha(self) -> str:
        """Get current git SHA if available."""
        try:
            import subprocess

            result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
            return result.stdout.strip()[:8]
        except Exception:
            return "unknown"


class ScoringRulesWatcher:
    """Watches scoring rules file for changes and triggers reload."""

    def __init__(
        self, engine: ConfigurableScoringEngine, config_path: str | None = None, debounce_seconds: float = 2.0
    ):
        """
        Initialize the watcher.

        Args:
            engine: Scoring engine to reload
            config_path: Path to watch (defaults to engine's config path)
            debounce_seconds: Time to wait before reloading
        """
        self.engine = engine
        self.config_path = Path(config_path or engine.rules_parser.rules_file)
        self.debounce_seconds = debounce_seconds
        self.observer = Observer()
        self.handler = ScoringRulesFileHandler(engine, debounce_seconds)
        self._started = False

    def start(self):
        """Start watching for file changes."""
        if self._started:
            logger.warning("Watcher already started")
            return

        # Watch the directory containing the config file
        watch_dir = self.config_path.parent

        self.observer.schedule(self.handler, str(watch_dir), recursive=False)

        self.observer.start()
        self._started = True

        logger.info(f"Started watching {self.config_path} for changes")

    def stop(self):
        """Stop watching for file changes."""
        if not self._started:
            return

        self.observer.stop()
        self.observer.join()
        self._started = False

        logger.info("Stopped watching for file changes")

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


# Singleton watcher instance
_watcher_instance: ScoringRulesWatcher | None = None
_watcher_lock = threading.Lock()


def get_watcher(engine: ConfigurableScoringEngine) -> ScoringRulesWatcher:
    """
    Get or create the singleton watcher instance.

    Args:
        engine: Scoring engine to watch

    Returns:
        ScoringRulesWatcher instance
    """
    global _watcher_instance

    with _watcher_lock:
        if _watcher_instance is None:
            _watcher_instance = ScoringRulesWatcher(engine)
        return _watcher_instance


def start_watching(engine: ConfigurableScoringEngine):
    """
    Start watching scoring rules for changes.

    Args:
        engine: Scoring engine to reload on changes
    """
    watcher = get_watcher(engine)
    watcher.start()


def stop_watching():
    """Stop watching scoring rules for changes."""
    global _watcher_instance

    with _watcher_lock:
        if _watcher_instance:
            _watcher_instance.stop()
            _watcher_instance = None
