# -*- coding: utf-8 -*-
"""Helpers de logging estruturado com sanitizacao de contexto."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def _sanitize_value(key: str, value: Any) -> Any:
    if value is None:
        return None
    if key == "arquivo":
        return Path(str(value)).name
    return value


def log_event(logger: logging.Logger, level: int, evento: str, **context: Any) -> None:
    payload = {"evento": evento}
    for key, value in context.items():
        payload[key] = _sanitize_value(key, value)
    logger.log(level, json.dumps(payload, ensure_ascii=False, default=str))
