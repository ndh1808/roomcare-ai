from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import secrets

import pytest
from PIL import Image
from sqlalchemy import select

from roomcare.db import Store, metadata, tickets


@pytest.fixture
def store(tmp_path):
    result = Store(f"sqlite:///{tmp_path / 'test.db'}")
    result.init_db()
    yield result
    result.engine.dispose()


def analysis():
    return {"category": "Nước", "priority": "Trung bình", "summary": "Vòi nước bị rò.", "source": "demo"}


def test_create_lookup_update_history_and_cross_connection(store):
    receipt = store.create_ticket("203", "Vòi nước bị rò", analysis())
    assert receipt["ticket_code"].startswith("RC-")
    assert len(receipt["tracking_token"]) >= 32
    assert receipt["history"][0]["status"] == "Đã gửi"
    assert "tracking_token_hash" not in receipt
    second = Store(str(store.engine.url))
    found = second.lookup_ticket(receipt["ticket_code"], receipt["tracking_token"])
    assert found["room"] == "203"
    assert "tracking_token" not in found
    assert "tracking_token_hash" not in found
    assert second.lookup_ticket(receipt["ticket_code"], "x" * 43) is None
    second.update_ticket(receipt["ticket_code"], "Đang xử lý", "Hẹn thợ chiều nay", "Nước", "Cao")
    updated = store.lookup_ticket(receipt["ticket_code"], receipt["tracking_token"])
    assert updated["status"] == "Đang xử lý"
    assert updated["priority"] == "Cao"
    assert updated["admin_note"] == "Hẹn thợ chiều nay"
    assert len(updated["history"]) == 2
    second.engine.dispose()


def test_token_is_hashed_at_rest(store):
    receipt = store.create_ticket("101", "Mất nước", analysis())
    with store.engine.connect() as connection:
        row = connection.execute(select(tickets)).mappings().one()
    assert row["tracking_token_hash"] != receipt["tracking_token"]
    assert len(row["tracking_token_hash"]) == 64
    assert receipt["tracking_token"] not in str(dict(row))


def test_invalid_lookup_cannot_enumerate_or_inject(store):
    receipt = store.create_ticket("101", "Mất nước", analysis())
    for code, token in [(receipt["ticket_code"], ""), ("' OR 1=1--", "a" * 43), ("RC-FFFFFFFFFF", receipt["tracking_token"]), (None, None)]:
        assert store.lookup_ticket(code, token) is None


def test_idempotent_submit(store):
    request_id = "example-request-id-1234567"
    first = store.create_ticket("101", "Mất nước", analysis(), request_id=request_id)
    again = store.create_ticket("101", "Mất nước", analysis(), request_id=request_id)
    assert first["ticket_code"] == again["ticket_code"]
    assert again["duplicate"] is True
    assert again["tracking_token"] is None
    assert len(store.list_tickets()) == 1


def test_retry_receipt_recovers_only_with_original_secret(store):
    token = secrets.token_urlsafe(32)
    request_id = "example-request-id-recover"
    first = store.create_ticket("101", "Mất nước", analysis(), request_id=request_id, tracking_token=token)
    again = store.create_ticket("101", "Mất nước", analysis(), request_id=request_id, tracking_token=token)
    wrong = store.create_ticket("101", "Mất nước", analysis(), request_id=request_id, tracking_token=secrets.token_urlsafe(32))
    assert again["tracking_token"] == first["tracking_token"] == token
    assert wrong["tracking_token"] is None
    assert len(store.list_tickets()) == 1
    with pytest.raises(ValueError, match="Khóa tra cứu"):
        store.create_ticket("101", "Mất nước", analysis(), tracking_token="weak")


def test_init_db_does_not_repeat_schema_operations(store, monkeypatch):
    def unexpected_call(*args, **kwargs):
        raise AssertionError("Schema initialization repeated after successful init")
    monkeypatch.setattr(metadata, "create_all", unexpected_call)
    store.init_db()


def test_validation_does_not_write_partial_ticket(store):
    with pytest.raises(ValueError):
        store.create_ticket("", "Mất nước", analysis())
    with pytest.raises(ValueError):
        store.create_ticket("101", "", analysis())
    with pytest.raises(ValueError):
        store.create_ticket("101", "x" * 4001, analysis())
    with pytest.raises(ValueError):
        store.create_ticket("101", "Mất nước", {"category": "injected", "priority": "Cao"})
    assert store.list_tickets() == []


def test_invalid_update_keeps_original(store):
    receipt = store.create_ticket("101", "Mất nước", analysis())
    with pytest.raises(ValueError):
        store.update_ticket(receipt["ticket_code"], "bad-status", "")
    with pytest.raises(ValueError):
        store.update_ticket("missing", "Đang xử lý", "")
    assert store.list_tickets()[0]["status"] == "Đã gửi"
    assert len(store.list_tickets()[0]["history"]) == 1


def test_image_is_shared_and_metadata_stripped(store):
    output = BytesIO()
    image = Image.new("RGB", (20, 20), "red")
    exif = Image.Exif()
    exif[270] = "private location"
    image.save(output, "JPEG", exif=exif)
    receipt = store.create_ticket("101", "", analysis(), image_bytes=output.getvalue(), image_mime="image/jpeg")
    found = store.lookup_ticket(receipt["ticket_code"], receipt["tracking_token"])
    assert found["image_bytes"]
    with Image.open(BytesIO(found["image_bytes"])) as cleaned:
        assert not cleaned.getexif()


def test_seed_is_idempotent(store):
    assert store.seed_demo() == 8
    assert store.seed_demo() == 0
    assert len(store.list_tickets()) == 8


def test_login_throttle_persists_between_connections(store):
    assert store.check_login_allowed("chu-tro")
    for _ in range(5):
        store.record_login_attempt("chu-tro", False)
    second = Store(str(store.engine.url))
    assert not second.check_login_allowed("CHU-TRO")
    store.record_login_attempt("chu-tro", True)
    assert second.check_login_allowed("chu-tro")
    second.engine.dispose()


def test_concurrent_requests_same_room(store):
    def create(index):
        return store.create_ticket("101", f"Sự cố nước {index}", analysis())
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(create, range(8)))
    assert len({row["ticket_code"] for row in results}) == 8
    assert len(store.list_tickets()) == 8
