from dataclasses import dataclass, field
import os
from pathlib import Path


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("PAPER_API_DATA_DIR", "state/paper-api")).resolve())
    api_key: str = field(default_factory=lambda: os.getenv("PAPER_LLM_API_KEY", ""))
    base_url: str = field(default_factory=lambda: os.getenv("PAPER_LLM_BASE_URL", "https://api.deepseek.com/v1"))
    model: str = field(default_factory=lambda: os.getenv("PAPER_LLM_MODEL", "deepseek-chat"))
    secure_cookie: bool = field(default_factory=lambda: os.getenv("PAPER_SECURE_COOKIE", "false").lower() == "true")
    origins: tuple = field(default_factory=lambda: tuple(os.getenv("PAPER_PUBLIC_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")))
    daily_imports: int = 3
    daily_actions: int = 50
    global_actions: int = field(default_factory=lambda: int(os.getenv("PAPER_GLOBAL_DAILY_ACTIONS", "5000")))
    max_bytes: int = 30 * 1024 * 1024
    max_pages: int = 100
    retention_days: int = 30
    aggregate_days: int = 180
    lease_seconds: int = 600

    @property
    def database(self):
        return self.data_dir / "papers.sqlite3"
