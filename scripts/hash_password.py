"""Create an ADMIN_PASSWORD_HASH without exposing the password in shell history."""

from getpass import getpass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from roomcare.security import hash_password


def main() -> None:
    password = getpass("Mật khẩu chủ trọ (ít nhất 12 ký tự): ")
    confirmation = getpass("Nhập lại mật khẩu: ")
    if password != confirmation:
        raise SystemExit("Mật khẩu nhập lại không khớp.")
    try:
        print(hash_password(password))
    except ValueError as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
