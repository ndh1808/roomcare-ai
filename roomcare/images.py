"""Validate, bound, and strip metadata from user image uploads."""

from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 12_000_000
MAX_EDGE = 1600


def validate_image(data: bytes) -> tuple[bytes, str]:
    if not isinstance(data, bytes) or not data:
        raise ValueError("Ảnh không hợp lệ hoặc rỗng.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Ảnh tối đa 5 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as check:
                if check.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("Chỉ hỗ trợ ảnh JPG, PNG hoặc WebP.")
                if check.width * check.height > MAX_PIXELS:
                    raise ValueError("Ảnh tối đa 12 triệu điểm ảnh.")
                check.verify()
            with Image.open(BytesIO(data)) as source:
                source.seek(0)
                oriented = ImageOps.exif_transpose(source)
                oriented.thumbnail((MAX_EDGE, MAX_EDGE))
                # A fresh pixel-only image avoids carrying EXIF, GPS, text or ICC metadata.
                if oriented.mode in {"RGBA", "LA"} or "transparency" in oriented.info:
                    rgba = oriented.convert("RGBA")
                    clean = Image.new("RGB", rgba.size, "white")
                    clean.paste(rgba, mask=rgba.getchannel("A"))
                else:
                    converted = oriented.convert("RGB")
                    clean = Image.new("RGB", converted.size)
                    clean.paste(converted)
                output = BytesIO()
                clean.save(output, format="JPEG", quality=85, optimize=True)
                return output.getvalue(), "image/jpeg"
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("Không đọc được ảnh. Hãy chọn một ảnh JPG, PNG hoặc WebP hợp lệ.") from exc
