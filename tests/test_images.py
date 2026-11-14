from io import BytesIO

import pytest
from PIL import Image, PngImagePlugin

from roomcare.images import MAX_UPLOAD_BYTES, validate_image


def test_png_is_resized_and_metadata_removed():
    output = BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("private", "GPS-like personal data")
    Image.new("RGBA", (2000, 100), (255, 0, 0, 50)).save(output, "PNG", pnginfo=metadata)
    result, mime = validate_image(output.getvalue())
    assert mime == "image/jpeg"
    with Image.open(BytesIO(result)) as image:
        assert image.width == 1600
        assert image.mode == "RGB"
        assert "private" not in image.info
        assert not image.getexif()


@pytest.mark.parametrize("value", [b"", b"not an image", b"<svg></svg>", b"x" * (MAX_UPLOAD_BYTES + 1)])
def test_bad_images_rejected(value):
    with pytest.raises(ValueError):
        validate_image(value)


def test_pixel_limit_rejects_small_compressed_large_image():
    output = BytesIO()
    Image.new("RGB", (4000, 3100), "white").save(output, "PNG")
    with pytest.raises(ValueError, match="12 triệu"):
        validate_image(output.getvalue())


def test_unsupported_gif_rejected():
    output = BytesIO()
    Image.new("RGB", (10, 10)).save(output, "GIF")
    with pytest.raises(ValueError, match="JPG"):
        validate_image(output.getvalue())
