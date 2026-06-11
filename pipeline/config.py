"""Unified configuration module for the Paper-to-WeChat Pipeline.

Reads configuration from ~/.paper-to-wechat/config.json with fallback to
environment variables. Implements the singleton pattern so config is loaded
once and shared across all modules.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Dict, Optional


@dataclass
class Config:
    """Pipeline configuration, loaded from file with env-var fallback.

    Singleton — use Config.get() to retrieve the shared instance.
    """

    wechat_appid: str = ""
    wechat_appsecret: str = ""
    data_dir: str = ""
    collector_port: int = 8899

    _instance: ClassVar[Optional["Config"]] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def get(cls) -> "Config":
        """Return the singleton Config instance, loading it on first access."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls._load()
        return cls._instance

    @classmethod
    def reload(cls) -> "Config":
        """Force-reload configuration from disk / env."""
        with cls._lock:
            cls._instance = cls._load()
        return cls._instance

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _default_config_path() -> Path:
        return Path.home() / ".paper-to-wechat" / "config.json"

    @classmethod
    def _load(cls) -> "Config":
        file_values: Dict[str, Any] = {}
        config_path = cls._default_config_path()
        if config_path.exists():
            try:
                with open(config_path, encoding="utf-8") as fh:
                    file_values = json.load(fh)
            except (json.JSONDecodeError, OSError):
                pass  # silently fall back to env vars

        return Config(
            wechat_appid=cls._resolve_str(
                file_values, "wechat_appid", "WECHAT_APPID", ""
            ),
            wechat_appsecret=cls._resolve_str(
                file_values, "wechat_appsecret", "WECHAT_APPSECRET", ""
            ),
            data_dir=cls._resolve_str(
                file_values,
                "data_dir",
                "PAPER_TO_WECHAT_DATA_DIR",
                str(Path.home() / "paper-to-wechat-data"),
            ),
            collector_port=cls._resolve_int(
                file_values, "collector_port", "PAPER_TO_WECHAT_COLLECTOR_PORT", 8899
            ),
        )

    @staticmethod
    def _resolve_str(
        file_values: Dict[str, Any],
        key: str,
        env_var: str,
        default: str,
    ) -> str:
        """Resolve a string config value: file > env > default."""
        if key in file_values and file_values[key] is not None:
            return str(file_values[key])
        env_val = os.environ.get(env_var)
        if env_val is not None:
            return env_val
        return default

    @staticmethod
    def _resolve_int(
        file_values: Dict[str, Any],
        key: str,
        env_var: str,
        default: int,
    ) -> int:
        """Resolve an integer config value: file > env > default."""
        if key in file_values and file_values[key] is not None:
            try:
                return int(file_values[key])
            except (TypeError, ValueError):
                pass
        env_val = os.environ.get(env_var)
        if env_val is not None:
            try:
                return int(env_val)
            except ValueError:
                pass
        return default
