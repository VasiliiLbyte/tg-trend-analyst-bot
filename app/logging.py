from __future__ import annotations

import logging
from dataclasses import dataclass


@dataclass(frozen=True)
class LoggingConfig:
    level: str


def configure_logging(cfg: LoggingConfig) -> None:
    level = getattr(logging, cfg.level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

