"""Exercise the actual Streamlit student/landlord workflow with separate sessions."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from roomcare.db import get_store


APP = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture
def app_environment(tmp_path, monkeypatch):
    database_url = f"sqlite:///{(tmp_path / 'ui-test.db').as_posix()}"
    for key, value in {
        "DATABASE_URL": database_url,
        "DEMO_MODE": "true",
        "GEMINI_API_KEY": "",
        "ADMIN_USERNAME": "chu-tro",
        "ADMIN_PASSWORD_HASH": "",
        "BUILDING_NAME": "Nhà trọ kiểm thử",
    }.items():
        monkeypatch.setenv(key, value)
    get_store.cache_clear()
    yield database_url
    get_store(database_url).engine.dispose()
    get_store.cache_clear()


def fresh_app():
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    assert not app.exception
    assert not app.error
    return app


def element(elements, label):
    matches = [item for item in elements if item.label == label]
    assert len(matches) == 1, f"Expected one {label!r}; got {[item.label for item in elements]}"
    return matches[0]


def click(app, label):
    element(app.button, label).click().run()
    assert not app.exception
    return app


def navigate(app, page):
    app.radio(key="navigation").set_value(page).run()
    assert not app.exception


def text_values(elements):
    return "\n".join(str(item.value) for item in elements)


def login(app, password="RoomCareDemo2026!"):
    navigate(app, "Chủ trọ")
    element(app.text_input, "Tên đăng nhập").set_value("chu-tro")
    element(app.text_input, "Mật khẩu").set_value(password)
    click(app, "Đăng nhập")


def test_student_to_landlord_to_fresh_tracking_session(app_environment):
    student = fresh_app()
    student.text_input(key="room_0").set_value("203")
    student.text_area(key="description_0").set_value("Vòi nước trong phòng bị rò liên tục từ tối qua.")
    click(student, "Phân tích sự cố →")
    assert not student.error
    assert "Phân tích demo" in text_values(student.markdown)
    assert student.session_state["pending_issue"]["analysis"]["category"] == "Nước"
    student.text_area(key="additional_details").set_value("Nước nhỏ xuống sàn cạnh bồn rửa.")
    click(student, "Gửi phiếu cho chủ trọ")
    assert not student.error
    receipt = student.session_state["receipt"]
    code, token = receipt["ticket_code"], receipt["tracking_token"]
    assert code in text_values(student.code)
    assert token in text_values(student.code)
    assert len(get_store(app_environment).list_tickets()) == 1

    # A new session cannot inspect the dashboard without authentication.
    landlord = fresh_app()
    login(landlord, "wrong-password")
    assert "mật khẩu không đúng" in text_values(landlord.error)
    assert not landlord.dataframe
    assert not landlord.metric
    assert code not in text_values(landlord.markdown)
    element(landlord.text_input, "Mật khẩu").set_value("RoomCareDemo2026!")
    click(landlord, "Đăng nhập")
    assert not landlord.error
    assert element(landlord.metric, "Tổng số phiếu").value == "1"
    assert code in landlord.dataframe[0].value["Mã phiếu"].tolist()
    element(landlord.selectbox, "Trạng thái mới").set_value("Đang xử lý")
    element(landlord.text_area, "Ghi chú cho sinh viên").set_value("Đã tiếp nhận, sẽ liên hệ thời gian kiểm tra.")
    click(landlord, "Lưu cập nhật")
    assert not landlord.error
    assert "Đã lưu cập nhật" in text_values(landlord.success)

    tracking = fresh_app()
    navigate(tracking, "Tra cứu phiếu")
    element(tracking.text_input, "Mã phiếu").set_value(code)
    element(tracking.text_input, "Khóa tra cứu").set_value("wrong-token-with-enough-length")
    click(tracking, "Tra cứu tình trạng")
    assert "Không tìm thấy phiếu" in text_values(tracking.error)
    assert not tracking.subheader
    element(tracking.text_input, "Khóa tra cứu").set_value(token)
    click(tracking, "Tra cứu tình trạng")
    assert not tracking.error
    assert code in text_values(tracking.subheader)
    assert "Đang xử lý" in text_values(tracking.markdown)
    assert "Đã tiếp nhận, sẽ liên hệ thời gian kiểm tra." in text_values(tracking.text)
    assert "Nước nhỏ xuống sàn" in text_values(tracking.text)

    click(landlord, "Đăng xuất")
    assert not landlord.dataframe
    assert not landlord.metric
    assert element(landlord.text_input, "Mật khẩu")
    navigate(landlord, "Báo sự cố")
    navigate(landlord, "Chủ trọ")
    assert not landlord.dataframe


def test_demo_seed_is_idempotent_and_report_uses_seeded_records(app_environment):
    app = fresh_app()
    login(app)
    click(app, "Nạp dữ liệu demo")
    assert not app.error
    assert element(app.metric, "Tổng số phiếu").value == "8"
    click(app, "Nạp dữ liệu demo")
    assert element(app.metric, "Tổng số phiếu").value == "8"
    assert "Đã thêm 0 phiếu mẫu" in text_values(app.success)
    click(app, "Tạo báo cáo quản lý")
    assert not app.error
    report = app.session_state["management_report"]
    assert report["source"] == "demo"
    assert "8" in report["text"]
    assert "Báo cáo demo" in text_values(app.markdown)
    assert report["text"] in text_values(app.text)
    click(app, "Đăng xuất")
    assert "management_report" not in app.session_state
    assert report["text"] not in text_values(app.text)


def test_empty_submission_keeps_database_empty(app_environment):
    app = fresh_app()
    click(app, "Phân tích sự cố →")
    assert "nhập số phòng" in text_values(app.error)
    app.text_input(key="room_0").set_value("A101")
    click(app, "Phân tích sự cố →")
    assert "mô tả sự cố hoặc thêm một ảnh" in text_values(app.error)
    assert get_store(app_environment).list_tickets() == []


def test_dangerous_text_is_visible_in_student_review(app_environment):
    app = fresh_app()
    app.text_input(key="room_0").set_value("101")
    app.text_area(key="description_0").set_value("Ổ cắm có khói và mùi khét.")
    click(app, "Phân tích sự cố →")
    assert app.session_state["pending_issue"]["analysis"]["emergency"] is True
    assert "Có dấu hiệu nguy hiểm" in text_values(app.error)
    assert "Khẩn cấp" in text_values(app.markdown)
    assert get_store(app_environment).list_tickets() == []


def test_expired_admin_session_cannot_read_dashboard(app_environment):
    app = fresh_app()
    login(app)
    click(app, "Nạp dữ liệu demo")
    assert app.dataframe
    app.session_state["admin_until"] = 1
    app.run()
    assert not app.exception
    assert not app.dataframe
    assert not app.metric
    assert element(app.text_input, "Tên đăng nhập")


def test_maximum_form_text_can_be_saved_with_supplement(app_environment):
    app = fresh_app()
    app.text_input(key="room_0").set_value("A" * 30)
    app.text_area(key="description_0").set_value("Vòi nước " + "a" * (3000 - len("Vòi nước ")))
    click(app, "Phân tích sự cố →")
    app.text_area(key="additional_details").set_value("b" * 950)
    click(app, "Gửi phiếu cho chủ trọ")
    assert not app.error
    receipt = app.session_state["receipt"]
    assert len(receipt["description"]) <= 4000
    assert len(get_store(app_environment).list_tickets()) == 1


def test_added_danger_escalates_before_ticket_is_saved(app_environment):
    app = fresh_app()
    app.text_input(key="room_0").set_value("101")
    app.text_area(key="description_0").set_value("Đèn trong phòng không sáng.")
    click(app, "Phân tích sự cố →")
    app.text_area(key="additional_details").set_value("Bây giờ ổ cắm có khói và mùi khét.").run()
    assert "Thông tin bổ sung có dấu hiệu nguy hiểm" in text_values(app.error)
    click(app, "Gửi phiếu cho chủ trọ")
    assert not app.error
    assert app.session_state["receipt"]["priority"] == "Khẩn cấp"
    assert app.session_state["receipt"]["analysis"]["emergency"] is True


def test_edit_keeps_original_draft_and_next_issue_starts_empty(app_environment):
    app = fresh_app()
    app.text_input(key="room_0").set_value("A101")
    app.text_area(key="description_0").set_value("Mạng Wi-Fi thường xuyên mất kết nối.")
    click(app, "Phân tích sự cố →")
    click(app, "Sửa mô tả")
    assert app.text_input(key="room_0").value == "A101"
    assert app.text_area(key="description_0").value == "Mạng Wi-Fi thường xuyên mất kết nối."
    app.session_state["last_analysis_at"] = 0
    click(app, "Phân tích sự cố →")
    click(app, "Gửi phiếu cho chủ trọ")
    assert not app.error
    click(app, "Báo một sự cố khác")
    assert app.text_input(key="room_1").value == ""
    assert app.text_area(key="description_1").value == ""
