"""
Structured logging configuration
Supports both JSON and text formats for different environments
"""
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from pythonjsonlogger import jsonlogger

from core.config import settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields"""

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)

        # Add custom fields
        log_record["timestamp"] = datetime.utcnow().isoformat()
        log_record["app"] = settings.app_name
        log_record["environment"] = settings.environment
        log_record["level"] = record.levelname
        log_record["logger"] = record.name

        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        # Remove internal fields
        for field in ["message", "msg"]:
            log_record.pop(field, None)


def setup_logging() -> None:
    """Configure logging based on environment settings"""
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)

    if settings.log_format == "json":
        # JSON format for production/structured logging
        formatter = CustomJsonFormatter(
            "%(timestamp)s %(level)s %(name)s %(message)s", timestamp=True
        )
    else:
        # Human-readable format for development
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Adjust third-party loggers
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.database_echo else logging.WARNING
    )


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter to add context to all log messages"""

    def __init__(self, logger: logging.Logger, extra: Optional[Dict[str, Any]] = None):
        super().__init__(logger, extra or {})

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Add context to log messages"""
        # Merge extra context
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra

        return msg, kwargs

    def with_context(self, **context) -> "LoggerAdapter":
        """Create a new logger with additional context"""
        new_extra = self.extra.copy()
        new_extra.update(context)
        return LoggerAdapter(self.logger, new_extra)


def get_logger(name: str, **context) -> LoggerAdapter:
    """
    Get a logger instance with optional context

    Args:
        name: Logger name (usually __name__)
        **context: Additional context to include in all logs

    Returns:
        LoggerAdapter instance

    Example:
        logger = get_logger(__name__, domain="d0_gateway", provider="pagespeed")
        logger.info("API call successful", status_code=200, duration_ms=150)
    """
    logger = logging.getLogger(name)
    return LoggerAdapter(logger, context)


# Initialize logging on import
setup_logging()
