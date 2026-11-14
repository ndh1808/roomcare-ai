"""Seed synthetic data. Never use this command with a real tenant database."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from roomcare.config import load_settings
from roomcare.db import get_store


def main() -> None:
    settings = load_settings()
    if not settings.demo_mode:
        raise SystemExit("Chỉ nạp dữ liệu mẫu khi DEMO_MODE=true.")
    store = get_store(settings.database_url)
    store.init_db()
    print(f"Đã thêm {store.seed_demo()} phiếu mẫu. Chạy lại không tạo bản sao.")


if __name__ == "__main__":
    main()
