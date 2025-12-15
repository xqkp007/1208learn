import logging
from typing import Optional


_configured = False


def configure_logging(level: Optional[str] = None) -> None:
    global _configured
    if _configured:
        return
    logging.basicConfig(
        level=getattr(logging, (level or "INFO").upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    _configured = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
