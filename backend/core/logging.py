"""Central logging configuration."""

import logging
from datetime import datetime, timezone


class KeyValueFormatter(logging.Formatter):
    """Emit concise machine-readable key-value log records."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, timezone.utc).isoformat()
        message = (
            record.getMessage()
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
        )
        return (
            f'timestamp="{timestamp}" level={record.levelname} '
            f'logger="{record.name}" message="{message}"'
        )


def configure_logging(level: str) -> None:
    """Configure the process root logger once for backend execution."""
    handler = logging.StreamHandler()
    handler.setFormatter(KeyValueFormatter())
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

