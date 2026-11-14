"""Configuration. Secrets are read at runtime and are never logged."""

from dataclasses import dataclass, field
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default=f"sqlite:///{(ROOT / 'data' / 'roomcare.db').as_posix()}", repr=False)
    gemini_api_key: str = field(default="", repr=False)
    gemini_model: str = "gemini-2.5-flash"
    admin_username: str = "chu-tro"
    admin_password_hash: str = field(default="", repr=False)
    demo_mode: bool = True
    building_name: str = "Nhà trọ An Nhiên"

    @property
    def shared_database(self) -> bool:
        return self.database_url.startswith(("postgresql", "postgres://"))

    def validate(self) -> None:
        from .security import is_password_hash_valid
        if not self.database_url.startswith(("sqlite", "postgresql", "postgres://")):
            raise ValueError("DATABASE_URL phải dùng SQLite hoặc PostgreSQL.")
        if self.admin_password_hash and not is_password_hash_valid(self.admin_password_hash):
            raise ValueError("ADMIN_PASSWORD_HASH không hợp lệ. Hãy tạo lại bằng scripts/hash_password.py.")
        if not self.demo_mode:
            if not self.shared_database:
                raise ValueError("Chế độ thật cần DATABASE_URL PostgreSQL dùng chung (ví dụ Supabase).")
            if not self.admin_password_hash:
                raise ValueError("Cần cấu hình ADMIN_PASSWORD_HASH trước khi mở chế độ thật.")
            if not self.admin_username.strip():
                raise ValueError("Cần cấu hình ADMIN_USERNAME.")


def load_settings() -> Settings:
    # dotenv_values avoids mutating process-wide environment across Streamlit sessions.
    try:
        from dotenv import dotenv_values
        values = dict(dotenv_values(ROOT / ".env"))
    except ImportError:
        values = {}
    try:
        import streamlit as st
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx(suppress_warning=True) is not None:
            try:
                values.update(dict(st.secrets))
            except FileNotFoundError:
                pass
    except ImportError:
        pass
    values.update(os.environ)
    default = Settings()
    raw_demo = str(values.get("DEMO_MODE", "true")).strip().lower()
    if raw_demo not in {"true", "false", "1", "0", "yes", "no"}:
        raise ValueError("DEMO_MODE phải là true hoặc false.")
    settings = Settings(
        database_url=str(values.get("DATABASE_URL") or default.database_url),
        gemini_api_key=str(values.get("GEMINI_API_KEY") or ""),
        gemini_model=str(values.get("GEMINI_MODEL") or default.gemini_model),
        admin_username=str(values.get("ADMIN_USERNAME") or default.admin_username),
        admin_password_hash=str(values.get("ADMIN_PASSWORD_HASH") or ""),
        demo_mode=raw_demo in {"true", "1", "yes"},
        building_name=str(values.get("BUILDING_NAME") or default.building_name),
    )
    settings.validate()
    return settings
