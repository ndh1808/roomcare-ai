"""RoomCare AI — a small, Vietnamese-first student maintenance desk."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone, timedelta
import html
import json
import secrets
import time
import uuid

import pandas as pd
import streamlit as st

from roomcare.ai import CATEGORIES, PRIORITIES, analyze_issue, enforce_safety, generate_report
from roomcare.config import load_settings
from roomcare.db import get_store
from roomcare.images import validate_image
from roomcare.security import authenticate

st.set_page_config(page_title="RoomCare AI · Chăm chút nơi bạn ở", page_icon="🏡", layout="wide")
STATUSES = ("Đã gửi", "Đang xử lý", "Hoàn thành")
VN_TZ = timezone(timedelta(hours=7))


def display_time(value):
    try:
        date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return date.astimezone(VN_TZ).strftime("%d/%m/%Y · %H:%M")
    except (TypeError, ValueError):
        return str(value)


def styling():
    st.markdown("""<style>
    @import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800&display=swap');
    html,body,[class*="css"],.stApp {font-family:'Be Vietnam Pro',sans-serif;}
    .stApp{background:#F5F7F5;color:#203B36;}
    .block-container{max-width:1180px;padding-top:2rem;padding-bottom:3rem;}
    h1,h2,h3{letter-spacing:-.035em;color:#163F36;}
    h1{font-size:2.8rem!important;line-height:1.18!important;font-weight:800!important;}
    .rc-brand{font-size:1.25rem;font-weight:800;color:#136A51;letter-spacing:-.5px;}
    .rc-brand span{font-size:.7rem;letter-spacing:1.6px;margin-left:12px;font-weight:500;color:#60756E;}
    .rc-hero{background:#E5EFE7;padding:32px 36px;border-radius:24px;margin:20px 0 24px;border:1px solid #D5E3D8;}
    .rc-eyebrow{font-size:.72rem;font-weight:700;letter-spacing:2px;color:#43735D;margin-bottom:14px;}
    .rc-hero p{max-width:640px;font-size:1rem;line-height:1.8;color:#526A60;margin-bottom:0;}
    .rc-step{font-size:.8rem;color:#4D7060;margin-top:24px;line-height:1.8;}
    .rc-pill{display:inline-block;padding:5px 10px;background:#E6F2EC;color:#126247;border-radius:30px;font-size:.75rem;font-weight:600;margin:0 5px 8px 0;}
    .rc-footer{color:#718079;font-size:.75rem;margin-top:40px;border-top:1px solid #DEE6DF;padding-top:18px;}
    div[data-testid="stForm"],div[data-testid="stVerticalBlockBorderWrapper"]>div{border-radius:18px;}
    div[data-testid="stForm"]{background:white;padding:24px;border-color:#DCE6DF;}
    div[data-testid="stMetric"]{background:white;border:1px solid #E0E8E2;border-radius:16px;padding:18px;}
    .stButton button,.stDownloadButton button{border-radius:10px;min-height:42px;}
    div[data-testid="stRadio"]>div{gap:12px;}
    @media(max-width:640px){.block-container{padding:4.5rem 1rem 2rem;}h1{font-size:2rem!important;}.rc-hero{padding:24px 20px;border-radius:18px;}.rc-brand span{display:block;margin:6px 0 0;}.rc-step{font-size:.72rem;}div[data-testid="stForm"]{padding:16px;}}
    </style>""", unsafe_allow_html=True)


def pills(*values):
    st.markdown("".join(f'<span class="rc-pill">{html.escape(str(v))}</span>' for v in values), unsafe_allow_html=True)


def analysis_card(analysis):
    pills(analysis["category"], analysis["priority"], "Gemini AI" if analysis["source"] == "gemini" else "Phân tích demo")
    st.text(analysis["summary"])
    if analysis.get("notice"):
        st.caption(analysis["notice"])
    if analysis.get("emergency"):
        st.error("Có dấu hiệu nguy hiểm. Rời xa khu vực, liên hệ chủ trọ và hỗ trợ khẩn cấp tại địa phương ngay; không chờ xử lý phiếu.")
    for advice in analysis.get("safe_advice", []):
        st.write("• " + advice)
    if analysis.get("follow_up_questions"):
        st.markdown("**Thông tin nên bổ sung cho chủ trọ**")
        for question in analysis["follow_up_questions"]:
            st.text("• " + question)


def receipt_card(receipt):
    st.success("Đã gửi phiếu. Chủ trọ có thể xem yêu cầu trong dashboard.")
    with st.container(border=True):
        st.subheader("Giữ lại thông tin tra cứu của bạn")
        st.caption("Cần cả mã phiếu và khóa bảo mật để xem tình trạng. Không chia sẻ khóa với người khác.")
        st.markdown("**Mã phiếu**")
        st.code(receipt["ticket_code"], language=None)
        token = receipt.get("tracking_token")
        if token:
            st.markdown("**Khóa tra cứu**")
            st.code(token, language=None)
            body = f"ROOMCARE AI\nMã phiếu: {receipt['ticket_code']}\nKhóa tra cứu: {token}\nPhòng: {receipt['room']}\nHãy giữ riêng thông tin này.\n"
            st.download_button("Lưu thông tin tra cứu", body, file_name=f"{receipt['ticket_code']}.txt", mime="text/plain", key="download_receipt")
        else:
            st.info("Phiếu đã được ghi nhận trước đó. Hãy dùng khóa tra cứu đã lưu từ lần gửi đầu tiên.")
    if st.button("Báo một sự cố khác", key="new_issue"):
        st.session_state.pop("receipt", None)
        st.session_state.pop("pending_issue", None)
        st.session_state.pop("issue_draft", None)
        st.session_state["form_number"] = st.session_state.get("form_number", 0) + 1
        st.rerun()


def student_page(settings, store):
    st.markdown('''<div class="rc-hero"><div class="rc-eyebrow">GÓC NHỎ AN TÂM · SINH VIÊN</div>
    <h1>Phòng có sự cố?<br>Để RoomCare giúp bạn.</h1>
    <p>Gửi ảnh hoặc kể lại điều đang xảy ra. RoomCare giúp làm rõ thông tin để chủ trọ tiếp nhận và theo dõi sửa chữa.</p>
    <div class="rc-step">01 &nbsp; Kể lại sự cố &nbsp;&nbsp; → &nbsp;&nbsp; 02 &nbsp; Kiểm tra tóm tắt &nbsp;&nbsp; → &nbsp;&nbsp; 03 &nbsp; Theo dõi phiếu</div></div>''', unsafe_allow_html=True)
    if st.session_state.get("receipt"):
        receipt_card(st.session_state["receipt"])
        return
    pending = st.session_state.get("pending_issue")
    if pending:
        st.subheader("02 / Kiểm tra trước khi gửi")
        with st.container(border=True):
            st.caption(f"Phòng {pending['room']} · Thông tin gợi ý cần được chủ trọ xác minh")
            analysis_card(pending["analysis"])
            if pending["image_bytes"]:
                st.image(pending["image_bytes"], caption="Ảnh đính kèm", width=320)
            with st.expander("Xem mô tả gốc"):
                st.text(pending["description"] or "Chỉ gửi hình ảnh.")
        extra = st.text_area("Bổ sung thông tin (không bắt buộc)", max_chars=950, placeholder="Ví dụ: Sự cố bắt đầu từ tối qua, chỉ xảy ra ở phòng em.", key="additional_details")
        st.caption("Phần bổ sung được gửi nguyên văn cho chủ trọ. Chọn “Sửa mô tả” nếu muốn AI phân tích lại.")
        combined_description = pending["description"] + ("\n\nBổ sung: " + extra.strip() if extra.strip() else "")
        final_analysis = enforce_safety(pending["analysis"], combined_description)
        if final_analysis["emergency"] and not pending["analysis"]["emergency"]:
            st.error("Thông tin bổ sung có dấu hiệu nguy hiểm. Phiếu được nâng lên Khẩn cấp; hãy rời xa khu vực và liên hệ hỗ trợ ngay.")
        left, right = st.columns(2)
        if left.button("Gửi phiếu cho chủ trọ", type="primary", use_container_width=True):
            try:
                receipt = store.create_ticket(pending["room"], combined_description, final_analysis, pending["image_bytes"], pending["image_mime"], pending["request_id"], tracking_token=pending["tracking_token"])
            except Exception:
                st.error("Chưa lưu được phiếu. Hãy thử lại; nội dung bạn nhập vẫn được giữ ở đây.")
            else:
                st.session_state["receipt"] = receipt
                st.session_state.pop("pending_issue", None)
                st.rerun()
        if right.button("Sửa mô tả", use_container_width=True):
            st.session_state["issue_draft"] = pending
            st.session_state.pop("pending_issue", None)
            st.rerun()
        return

    main, aside = st.columns([1.65, 1], gap="large")
    with main:
        st.subheader("01 / Báo sự cố")
        n = st.session_state.get("form_number", 0)
        draft = st.session_state.get("issue_draft", {})
        with st.form(f"issue_form_{n}"):
            room = st.text_input("Số phòng", value=draft.get("room", ""), max_chars=30, placeholder="Ví dụ: A203", key=f"room_{n}")
            description = st.text_area("Phòng bạn đang gặp vấn đề gì?", value=draft.get("description", ""), height=140, max_chars=3000, placeholder="Ví dụ: Điều hòa bật lên nhưng không mát, đèn trên máy nhấp nháy từ tối qua.", key=f"description_{n}")
            photo = st.file_uploader("Ảnh sự cố (không bắt buộc)", type=["jpg", "jpeg", "png", "webp"], help="Tối đa 5 MB. Chụp từ vị trí an toàn, tránh giấy tờ và thông tin cá nhân.", key=f"photo_{n}")
            remove_photo = False
            if draft.get("image_bytes"):
                st.caption("Ảnh đã chọn vẫn được giữ. Tải ảnh mới để thay thế.")
                remove_photo = st.checkbox("Bỏ ảnh đã chọn")
            if settings.gemini_api_key:
                st.caption("Nếu bạn đồng ý, mô tả và ảnh sẽ được gửi tới Google Gemini để phân tích. Nếu không, ứng dụng dùng phân loại demo.")
                consent = st.checkbox("Tôi đồng ý gửi mô tả và ảnh tới Gemini", key=f"consent_{n}")
            else:
                consent = False
                st.caption("Chưa bật Gemini: ứng dụng dùng quy tắc demo và không phân tích nội dung ảnh.")
            submitted = st.form_submit_button("Phân tích sự cố →", type="primary", use_container_width=True)
        if submitted:
            if not room.strip():
                st.error("Bạn cần nhập số phòng.")
            elif not description.strip() and not photo and (not draft.get("image_bytes") or remove_photo):
                st.error("Hãy mô tả sự cố hoặc thêm một ảnh.")
            elif time.time() - st.session_state.get("last_analysis_at", 0) < 5:
                st.warning("Vui lòng đợi vài giây trước khi phân tích lại.")
            else:
                image_bytes = draft.get("image_bytes") if not remove_photo else None
                image_mime = draft.get("image_mime") if image_bytes else None
                try:
                    if photo:
                        image_bytes, image_mime = validate_image(photo.getvalue())
                except ValueError as error:
                    st.error(str(error))
                    return
                st.session_state["last_analysis_at"] = time.time()
                with st.spinner("Đang đọc thông tin sự cố…"):
                    analysis = analyze_issue(description.strip(), image_bytes, image_mime, settings.gemini_api_key if consent else "", settings.gemini_model)
                st.session_state["pending_issue"] = dict(room=room.strip(), description=description.strip(), image_bytes=image_bytes, image_mime=image_mime, analysis=analysis, request_id=str(uuid.uuid4()), tracking_token=secrets.token_urlsafe(32))
                st.session_state.pop("additional_details", None)
                st.rerun()
    with aside:
        st.subheader("Một mô tả rõ, bớt chờ lâu")
        with st.container(border=True):
            st.markdown("**Thiết bị nào gặp lỗi?**")
            st.write("Điều hòa, vòi nước, ổ điện, Wi-Fi…")
            st.markdown("**Bạn quan sát được gì?**")
            st.write("Kể hiện tượng và thời điểm bắt đầu. Bạn không cần tự tìm nguyên nhân.")
            st.markdown("**Ảnh có thể giúp làm rõ**")
            st.write("Chụp toàn cảnh và vị trí sự cố từ nơi an toàn.")
        st.warning("Nếu có khói, tia lửa, mùi gas hoặc dấu hiệu rò điện: rời xa khu vực và liên hệ hỗ trợ ngay. Không chờ phản hồi từ ứng dụng.")


def ticket_detail(ticket):
    pills(ticket["status"], ticket["category"], ticket["priority"])
    st.subheader(ticket["ticket_code"])
    st.caption(f"Phòng {ticket['room']} · Gửi lúc {display_time(ticket['created_at'])}")
    st.text(ticket["ai_summary"])
    with st.expander("Mô tả và ảnh đã gửi"):
        st.text(ticket["description"] or "Chỉ gửi hình ảnh.")
        if ticket.get("image_bytes"):
            st.image(ticket["image_bytes"], width=360)
    st.markdown("**Tiến trình xử lý**")
    for event in ticket.get("history", []):
        st.write(f"{display_time(event['created_at'])} — {event['status']}")
        if event.get("note"):
            st.text(event["note"])


def tracking_page(store):
    st.title("Phiếu của bạn đến đâu rồi?")
    st.write("Nhập thông tin đã nhận khi gửi phiếu để xem cập nhật từ chủ trọ.")
    with st.form("tracking_form"):
        code = st.text_input("Mã phiếu", placeholder="RC-…", max_chars=60)
        token = st.text_input("Khóa tra cứu", type="password", max_chars=150)
        submitted = st.form_submit_button("Tra cứu tình trạng", type="primary")
    if submitted:
        if not code.strip() or not token.strip():
            st.warning("Hãy nhập cả mã phiếu và khóa tra cứu.")
            return
        try:
            ticket = store.lookup_ticket(code.strip().upper(), token.strip())
        except Exception:
            st.error("Chưa thể tra cứu lúc này. Vui lòng thử lại sau.")
            return
        if ticket:
            with st.container(border=True):
                ticket_detail(ticket)
        else:
            st.error("Không tìm thấy phiếu với thông tin này. Hãy kiểm tra lại mã phiếu và khóa tra cứu.")


def admin_login(settings, store):
    st.title("Không gian chủ trọ")
    st.write("Theo dõi những việc cần làm để mỗi căn phòng đều được chăm sóc.")
    if settings.demo_mode and not settings.admin_password_hash:
        st.info("Tài khoản demo: chu-tro / RoomCareDemo2026! · Chỉ dùng dữ liệu giả lập.")
    with st.form("login_form"):
        username = st.text_input("Tên đăng nhập", max_chars=80)
        password = st.text_input("Mật khẩu", type="password", max_chars=256)
        login = st.form_submit_button("Đăng nhập", type="primary")
    if login:
        # A single configured-account bucket prevents guessing alternate usernames
        # from bypassing the persistent login limit.
        bucket = settings.admin_username
        if not store.check_login_allowed(bucket):
            st.error("Có nhiều lần đăng nhập không thành công. Vui lòng thử lại sau 15 phút.")
            return
        success = authenticate(username, password, settings)
        store.record_login_attempt(bucket, success)
        if success:
            st.session_state["admin_until"] = time.time() + 3600
            st.rerun()
        else:
            st.error("Tên đăng nhập hoặc mật khẩu không đúng.")


def dashboard(settings, store):
    if st.session_state.get("admin_until", 0) < time.time():
        st.session_state.pop("management_report", None)
        admin_login(settings, store)
        return
    title, exit_column = st.columns([5, 1])
    title.title("Chăm sóc từng căn phòng")
    if exit_column.button("Đăng xuất", use_container_width=True):
        st.session_state.pop("admin_until", None)
        st.session_state.pop("management_report", None)
        st.rerun()
    st.caption(f"{settings.building_name} · Phiên quản lý kéo dài 60 phút")
    if settings.demo_mode:
        with st.expander("Dữ liệu mẫu cho buổi demo"):
            st.write("Thêm bộ sự cố giả lập. Bấm lại không tạo bản sao.")
            if st.button("Nạp dữ liệu demo"):
                count = store.seed_demo()
                st.success(f"Đã thêm {count} phiếu mẫu.")
    tickets = store.list_tickets()
    fingerprint = tuple((t["ticket_code"], t["updated_at"]) for t in tickets)
    if st.session_state.get("report_fingerprint") != fingerprint:
        st.session_state.pop("management_report", None)
    metrics = st.columns(4)
    metrics[0].metric("Tổng số phiếu", len(tickets))
    metrics[1].metric("Cần tiếp nhận", sum(t["status"] == "Đã gửi" for t in tickets))
    metrics[2].metric("Đang xử lý", sum(t["status"] == "Đang xử lý" for t in tickets))
    metrics[3].metric("Cần ưu tiên", sum(t["priority"] in {"Cao", "Khẩn cấp"} and t["status"] != "Hoàn thành" for t in tickets))
    manage, report_tab = st.tabs(["Danh sách & xử lý", "Tổng quan & báo cáo AI"])
    with manage:
        st.subheader("Hôm nay cần xử lý gì?")
        filters = st.columns(4)
        status_filter = filters[0].selectbox("Trạng thái", ["Tất cả", *STATUSES])
        category_filter = filters[1].selectbox("Nhóm sự cố", ["Tất cả", *CATEGORIES])
        room_filter = filters[2].selectbox("Phòng", ["Tất cả", *sorted({t['room'] for t in tickets})])
        priority_filter = filters[3].selectbox("Ưu tiên", ["Tất cả", *PRIORITIES])
        selected = [t for t in tickets if (status_filter == "Tất cả" or t["status"] == status_filter) and (category_filter == "Tất cả" or t["category"] == category_filter) and (room_filter == "Tất cả" or t["room"] == room_filter) and (priority_filter == "Tất cả" or t["priority"] == priority_filter)]
        selected.sort(key=lambda t: (t["status"] == "Hoàn thành", -PRIORITIES.index(t["priority"]), t["created_at"]))
        if not selected:
            st.info("Chưa có phiếu phù hợp. Phiếu mới từ sinh viên sẽ xuất hiện tại đây.")
        else:
            rows = [{"Mã phiếu": t["ticket_code"], "Phòng": t["room"], "Nhóm": t["category"], "Ưu tiên": t["priority"], "Trạng thái": t["status"], "Tóm tắt": t["ai_summary"]} for t in selected]
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            chosen_code = st.selectbox("Chọn phiếu để xử lý", [t["ticket_code"] for t in selected], format_func=lambda c: next(f"{c} · Phòng {t['room']} · {t['category']}" for t in selected if t["ticket_code"] == c))
            chosen = next(t for t in selected if t["ticket_code"] == chosen_code)
            with st.container(border=True):
                ticket_detail(chosen)
            with st.form(f"update_{chosen_code}_{chosen['updated_at']}"):
                st.markdown("**Cập nhật phiếu**")
                new_status = st.selectbox("Trạng thái mới", STATUSES, index=STATUSES.index(chosen["status"]))
                cols = st.columns(2)
                category = cols[0].selectbox("Xác nhận nhóm sự cố", CATEGORIES, index=CATEGORIES.index(chosen["category"]))
                priority = cols[1].selectbox("Xác nhận mức ưu tiên", PRIORITIES, index=PRIORITIES.index(chosen["priority"]))
                note = st.text_area("Ghi chú cho sinh viên", value=chosen.get("admin_note", ""), max_chars=2000, placeholder="Ví dụ: Thợ sẽ đến kiểm tra lúc 14:00 ngày mai.")
                st.caption("Ghi chú này hiển thị cho người giữ khóa tra cứu. Không ghi thông tin nội bộ hoặc mật khẩu.")
                updated = st.form_submit_button("Lưu cập nhật", type="primary")
            if updated:
                store.update_ticket(chosen_code, new_status, note, category=category, priority=priority)
                st.session_state.pop("management_report", None)
                st.session_state["update_success"] = True
                st.rerun()
        if st.session_state.pop("update_success", False):
            st.success("Đã lưu cập nhật. Sinh viên có thể tra cứu tình trạng mới.")
        if st.button("Làm mới danh sách"):
            st.rerun()
    with report_tab:
        st.subheader("Nhìn rõ các sự cố thường gặp")
        if tickets:
            chart_a, chart_b = st.columns(2)
            chart_a.markdown("**Theo nhóm sự cố**")
            chart_a.bar_chart(pd.Series(Counter(t["category"] for t in tickets), name="Số phiếu"), color="#238261")
            chart_b.markdown("**Theo trạng thái**")
            chart_b.bar_chart(pd.Series(Counter(t["status"] for t in tickets), name="Số phiếu"), color="#86AB8D")
            st.caption("Báo cáo tính trên toàn bộ phiếu. Gemini chỉ nhận số liệu tổng hợp; không nhận ảnh, mô tả gốc hoặc khóa tra cứu.")
            if st.button("Tạo báo cáo quản lý", type="primary"):
                with st.spinner("Đang tổng hợp các việc cần ưu tiên…"):
                    st.session_state["management_report"] = generate_report(tickets, settings.gemini_api_key, settings.gemini_model)
                    st.session_state["report_fingerprint"] = fingerprint
            report = st.session_state.get("management_report")
            if report:
                pills("Gemini AI" if report["source"] == "gemini" else "Báo cáo demo")
                st.text(report["text"])
                st.caption(report.get("notice", ""))
                st.download_button("Tải báo cáo", report["text"], file_name="roomcare-bao-cao.txt", mime="text/plain")
        else:
            st.info("Báo cáo sẽ xuất hiện khi có phiếu. Bạn có thể nạp dữ liệu mẫu để thử.")


def main():
    styling()
    st.markdown('<div class="rc-brand">⌂ &nbsp; RoomCare AI <span>CHĂM CHÚT NƠI BẠN Ở</span></div>', unsafe_allow_html=True)
    try:
        settings = load_settings()
        store = get_store(settings.database_url)
        store.init_db()
    except ValueError as error:
        st.error(str(error))
        st.info("Chủ ứng dụng xem hướng dẫn cấu hình trong README và docs/DEPLOYMENT.md.")
        st.stop()
    except Exception:
        st.error("Chưa kết nối được cơ sở dữ liệu. Chủ ứng dụng cần kiểm tra cấu hình và quyền kết nối.")
        st.stop()
    if settings.demo_mode:
        st.caption("BẢN DEMO · Chỉ sử dụng dữ liệu giả lập." + (" Dữ liệu đang lưu trên máy chạy ứng dụng." if not settings.shared_database else " Dữ liệu dùng chung giữa các thiết bị."))
    nav = st.radio("Điều hướng", ["Báo sự cố", "Tra cứu phiếu", "Chủ trọ"], horizontal=True, label_visibility="collapsed", key="navigation")
    try:
        if nav == "Báo sự cố":
            student_page(settings, store)
        elif nav == "Tra cứu phiếu":
            tracking_page(store)
        else:
            dashboard(settings, store)
    except Exception:
        st.error("Thao tác chưa hoàn tất. Vui lòng thử lại; ứng dụng không hiển thị chi tiết kết nối để bảo vệ dữ liệu.")
    st.markdown('<div class="rc-footer">RoomCare AI · Một nơi ở tốt hơn, bắt đầu từ một phản hồi.<br>AI hỗ trợ tiếp nhận; chủ trọ và người có chuyên môn xác minh sự cố.</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
