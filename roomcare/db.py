"""Shared persistence for SQLite demos and PostgreSQL/Supabase deployment.

PostgreSQL tables live in the private ``roomcare`` schema, not the default
Supabase Data API ``public`` schema. Never expose this schema through the API.
"""

from datetime import datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import threading
import uuid

from sqlalchemy import (
    JSON, Column, ForeignKey, Integer, LargeBinary, MetaData, String, Table,
    Text, create_engine, delete, event, func, insert, select, text, update,
)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from .images import validate_image

CATEGORIES = ("Điện", "Nước", "Điều hòa", "Internet", "Nội thất", "Khác")
PRIORITIES = ("Thấp", "Trung bình", "Cao", "Khẩn cấp")
STATUSES = ("Đã gửi", "Đang xử lý", "Hoàn thành")

metadata = MetaData(schema="roomcare")
rooms = Table(
    "rooms", metadata,
    Column("id", String(36), primary_key=True),
    Column("room_code", String(30), nullable=False, unique=True),
)
tickets = Table(
    "tickets", metadata,
    Column("id", String(36), primary_key=True),
    Column("ticket_code", String(32), nullable=False, unique=True),
    Column("room_id", String(36), ForeignKey("roomcare.rooms.id"), nullable=False),
    Column("room", String(30), nullable=False),
    Column("description", Text, nullable=False),
    Column("category", String(30), nullable=False),
    Column("priority", String(30), nullable=False),
    Column("ai_summary", Text, nullable=False),
    Column("analysis", JSON, nullable=False),
    Column("status", String(30), nullable=False),
    Column("admin_note", Text, nullable=False, default=""),
    Column("created_at", String(40), nullable=False, index=True),
    Column("updated_at", String(40), nullable=False),
    Column("tracking_token_hash", String(64), nullable=False),
    Column("request_id", String(128), unique=True),
    Column("image_bytes", LargeBinary),
    Column("image_mime", String(30)),
)
ticket_events = Table(
    "ticket_events", metadata,
    Column("id", String(36), primary_key=True),
    Column("ticket_id", String(36), ForeignKey("roomcare.tickets.id"), nullable=False, index=True),
    Column("status", String(30), nullable=False),
    Column("note", Text, nullable=False),
    Column("created_at", String(40), nullable=False),
)
login_attempts = Table(
    "login_attempts", metadata,
    Column("id", String(36), primary_key=True),
    Column("username_hash", String(64), nullable=False, index=True),
    Column("created_at", String(40), nullable=False),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _normalise_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url[len("postgres://"):]
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url[len("postgresql://"):]
    return database_url


class Store:
    def __init__(self, database_url: str):
        url = make_url(_normalise_url(database_url))
        if url.get_backend_name() not in {"sqlite", "postgresql"}:
            raise ValueError("Chỉ hỗ trợ SQLite và PostgreSQL.")
        kwargs = {"pool_pre_ping": True, "hide_parameters": True}
        if url.get_backend_name() == "sqlite":
            if url.database and url.database != ":memory:":
                Path(url.database).expanduser().parent.mkdir(parents=True, exist_ok=True)
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
            if not url.database or url.database == ":memory:":
                kwargs["poolclass"] = StaticPool
        else:
            kwargs["connect_args"] = {"connect_timeout": 10}
        self.engine = create_engine(url, **kwargs)
        self._initialized = False
        self._init_lock = threading.Lock()
        self.is_sqlite = url.get_backend_name() == "sqlite"
        if self.is_sqlite:
            self.engine = self.engine.execution_options(schema_translate_map={"roomcare": None})
            @event.listens_for(self.engine, "connect")
            def set_sqlite_options(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.close()

    def init_db(self) -> None:
        if self._initialized:
            return
        with self._init_lock:
            if self._initialized:
                return
            if not self.is_sqlite:
                with self.engine.begin() as connection:
                    connection.execute(text("CREATE SCHEMA IF NOT EXISTS roomcare"))
                    connection.execute(text("REVOKE ALL ON SCHEMA roomcare FROM PUBLIC"))
            metadata.create_all(self.engine)
            self._initialized = True

    @staticmethod
    def _clean(row) -> dict:
        result = dict(row)
        result.pop("tracking_token_hash", None)
        result.pop("request_id", None)
        return result

    def _with_history(self, connection, row) -> dict:
        result = self._clean(row)
        history = connection.execute(
            select(ticket_events.c.status, ticket_events.c.note, ticket_events.c.created_at)
            .where(ticket_events.c.ticket_id == result["id"])
            .order_by(ticket_events.c.created_at)
        ).mappings().all()
        result["history"] = [dict(item) for item in history]
        return result

    def create_ticket(self, room: str, description: str, analysis: dict,
                      image_bytes: bytes | None = None, image_mime: str | None = None,
                      request_id: str | None = None, *, tracking_token: str | None = None) -> dict:
        room = str(room).strip()
        description = str(description).strip()
        if not room or len(room) > 30 or any(ord(ch) < 32 for ch in room):
            raise ValueError("Số phòng cần từ 1 đến 30 ký tự.")
        if len(description) > 4000 or (not description and not image_bytes):
            raise ValueError("Hãy nhập mô tả (tối đa 4.000 ký tự) hoặc thêm ảnh.")
        if not isinstance(analysis, dict):
            raise ValueError("Kết quả phân tích không hợp lệ.")
        category = analysis.get("category", "Khác")
        priority = analysis.get("priority", "Trung bình")
        summary = str(analysis.get("summary") or analysis.get("ai_summary") or description[:500])[:1200]
        if category not in CATEGORIES or priority not in PRIORITIES:
            raise ValueError("Phân loại hoặc mức ưu tiên không hợp lệ.")
        if len(json.dumps(analysis, ensure_ascii=False)) > 30000:
            raise ValueError("Kết quả phân tích quá dài.")
        if request_id is not None and (not isinstance(request_id, str) or not 16 <= len(request_id) <= 128):
            raise ValueError("Mã yêu cầu không hợp lệ.")
        if image_bytes is not None:
            image_bytes, image_mime = validate_image(image_bytes)
        elif image_mime:
            raise ValueError("Thiếu nội dung ảnh.")
        supplied_token = tracking_token
        if supplied_token is not None and (not isinstance(supplied_token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", supplied_token)):
            raise ValueError("Khóa tra cứu không hợp lệ.")
        tracking_token = supplied_token or secrets.token_urlsafe(32)

        def duplicate_result(connection, existing):
            # A retry may return the same server-generated token only when the
            # caller still possesses it. No plaintext token is stored in the DB.
            retry_token = supplied_token if supplied_token and hmac.compare_digest(_hash(supplied_token), existing["tracking_token_hash"]) else None
            return {**self._with_history(connection, existing), "tracking_token": retry_token, "duplicate": True}
        ticket_id = str(uuid.uuid4())
        code = "RC-" + secrets.token_hex(5).upper()
        now = _now()
        try:
            with self.engine.begin() as connection:
                if request_id:
                    existing = connection.execute(select(tickets).where(tickets.c.request_id == request_id)).mappings().first()
                    if existing:
                        return duplicate_result(connection, existing)
                room_id = connection.execute(select(rooms.c.id).where(rooms.c.room_code == room)).scalar_one_or_none()
                if room_id is None:
                    room_id = str(uuid.uuid4())
                    # Savepoint allows another concurrent request to create the same room.
                    try:
                        with connection.begin_nested():
                            connection.execute(insert(rooms).values(id=room_id, room_code=room))
                    except IntegrityError:
                        room_id = connection.execute(select(rooms.c.id).where(rooms.c.room_code == room)).scalar_one()
                connection.execute(insert(tickets).values(
                    id=ticket_id, ticket_code=code, room_id=room_id, room=room,
                    description=description, category=category, priority=priority,
                    ai_summary=summary, analysis=analysis, status=STATUSES[0], admin_note="",
                    created_at=now, updated_at=now, tracking_token_hash=_hash(tracking_token),
                    request_id=request_id, image_bytes=image_bytes, image_mime=image_mime,
                ))
                connection.execute(insert(ticket_events).values(
                    id=str(uuid.uuid4()), ticket_id=ticket_id, status=STATUSES[0],
                    note="Đã tiếp nhận yêu cầu.", created_at=now,
                ))
                row = connection.execute(select(tickets).where(tickets.c.id == ticket_id)).mappings().one()
                return {**self._with_history(connection, row), "tracking_token": tracking_token, "duplicate": False}
        except IntegrityError:
            if request_id:
                with self.engine.connect() as connection:
                    existing = connection.execute(select(tickets).where(tickets.c.request_id == request_id)).mappings().first()
                    if existing:
                        return duplicate_result(connection, existing)
            raise

    def lookup_ticket(self, ticket_code: str, tracking_token: str) -> dict | None:
        if not isinstance(ticket_code, str) or not isinstance(tracking_token, str):
            return None
        code = ticket_code.strip().upper()
        if not re.fullmatch(r"RC-[A-F0-9]{10}", code) or not 16 <= len(tracking_token) <= 128:
            return None
        with self.engine.connect() as connection:
            row = connection.execute(select(tickets).where(tickets.c.ticket_code == code)).mappings().first()
            expected = row["tracking_token_hash"] if row else "0" * 64
            valid = hmac.compare_digest(_hash(tracking_token.strip()), expected)
            return self._with_history(connection, row) if row and valid else None

    def list_tickets(self) -> list[dict]:
        """Admin-only service: the caller must authenticate before calling."""
        with self.engine.connect() as connection:
            rows = connection.execute(select(tickets).order_by(tickets.c.created_at.desc())).mappings().all()
            return [self._with_history(connection, row) for row in rows]

    def update_ticket(self, ticket_code: str, status: str, admin_note: str,
                      category: str | None = None, priority: str | None = None) -> None:
        """Admin-only service. Notes are visible to the tenant who holds the token."""
        if status not in STATUSES:
            raise ValueError("Trạng thái không hợp lệ.")
        if category is not None and category not in CATEGORIES:
            raise ValueError("Phân loại không hợp lệ.")
        if priority is not None and priority not in PRIORITIES:
            raise ValueError("Mức ưu tiên không hợp lệ.")
        if not isinstance(admin_note, str) or len(admin_note) > 2000:
            raise ValueError("Ghi chú tối đa 2.000 ký tự.")
        with self.engine.begin() as connection:
            row = connection.execute(select(tickets.c.id).where(tickets.c.ticket_code == ticket_code)).first()
            if row is None:
                raise ValueError("Không tìm thấy phiếu.")
            now = _now()
            changes = dict(status=status, admin_note=admin_note.strip(), updated_at=now)
            if category is not None:
                changes["category"] = category
            if priority is not None:
                changes["priority"] = priority
            connection.execute(update(tickets).where(tickets.c.id == row.id).values(**changes))
            connection.execute(insert(ticket_events).values(
                id=str(uuid.uuid4()), ticket_id=row.id, status=status,
                note=admin_note.strip() or "Chủ trọ cập nhật phiếu.", created_at=now,
            ))

    def check_login_allowed(self, username: str) -> bool:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat(timespec="microseconds")
        with self.engine.connect() as connection:
            count = connection.execute(select(func.count()).select_from(login_attempts).where(
                login_attempts.c.username_hash == _hash(username.strip().casefold()),
                login_attempts.c.created_at >= cutoff,
            )).scalar_one()
        return count < 5

    def record_login_attempt(self, username: str, success: bool) -> None:
        username_hash = _hash(username.strip().casefold())
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat(timespec="microseconds")
        with self.engine.begin() as connection:
            connection.execute(delete(login_attempts).where(login_attempts.c.created_at < cutoff))
            if success:
                connection.execute(delete(login_attempts).where(login_attempts.c.username_hash == username_hash))
            else:
                connection.execute(insert(login_attempts).values(
                    id=str(uuid.uuid4()), username_hash=username_hash, created_at=_now(),
                ))

    def seed_demo(self) -> int:
        """Insert synthetic fixtures once; caller must restrict to explicit demo mode."""
        path = Path(__file__).resolve().parents[1] / "data" / "demo_tickets.json"
        fixtures = json.loads(path.read_text(encoding="utf-8"))
        count = 0
        for index, fixture in enumerate(fixtures):
            ticket = self.create_ticket(
                fixture["room"], fixture["description"], fixture["analysis"],
                request_id=f"roomcare-demo-fixture-v1-{index:03d}",
            )
            if ticket["duplicate"]:
                continue
            count += 1
            if fixture.get("status", STATUSES[0]) != STATUSES[0] or fixture.get("admin_note"):
                self.update_ticket(ticket["ticket_code"], fixture.get("status", STATUSES[0]), fixture.get("admin_note", ""))
        return count


@lru_cache(maxsize=4)
def get_store(database_url: str) -> Store:
    return Store(database_url)
