"""Tests for POST /listings/upload — validates the fix for the Tier 2 issue
where the endpoint trusted client-supplied Content-Type with no size limit.
See docs/DOCUMENTATION.md §7.
"""

from io import BytesIO

from PIL import Image


def _png_bytes(size: tuple[int, int] = (10, 10)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color="red").save(buffer, format="PNG")
    return buffer.getvalue()


async def test_upload_valid_png_succeeds(client, verified_host):
    headers = {"Authorization": f"Bearer {verified_host['token']}"}
    files = {"file": ("photo.png", _png_bytes(), "image/png")}
    response = await client.post("/listings/upload", headers=headers, files=files)
    assert response.status_code == 200
    assert response.json()["url"].endswith(".png")


async def test_upload_rejects_non_image_disguised_as_png(client, verified_host):
    """A real Tier 2 exploit: a non-image file with a spoofed Content-Type
    and .png filename. Must be rejected by decoding the actual bytes, not by
    trusting what the client claims."""
    headers = {"Authorization": f"Bearer {verified_host['token']}"}
    files = {"file": ("evil.png", b"not actually an image", "image/png")}
    response = await client.post("/listings/upload", headers=headers, files=files)
    assert response.status_code == 400


async def test_upload_rejects_oversized_file(client, verified_host):
    headers = {"Authorization": f"Bearer {verified_host['token']}"}
    oversized = b"\x00" * (5 * 1024 * 1024 + 1)
    files = {"file": ("big.png", oversized, "image/png")}
    response = await client.post("/listings/upload", headers=headers, files=files)
    assert response.status_code == 413


async def test_upload_strips_exif_metadata(client, verified_host):
    buffer = BytesIO()
    image = Image.new("RGB", (10, 10), color="blue")
    exif = image.getexif()
    exif[0x9286] = "sensitive location comment"  # UserComment tag
    image.save(buffer, format="JPEG", exif=exif)

    headers = {"Authorization": f"Bearer {verified_host['token']}"}
    files = {"file": ("photo.jpg", buffer.getvalue(), "image/jpeg")}
    response = await client.post("/listings/upload", headers=headers, files=files)
    assert response.status_code == 200

    saved_path = "." + response.json()["url"]  # UPLOAD_DIR is api/uploads
    saved = Image.open(saved_path)
    assert not saved.getexif()


async def test_upload_requires_auth(client):
    files = {"file": ("photo.png", _png_bytes(), "image/png")}
    response = await client.post("/listings/upload", files=files)
    assert response.status_code == 401
