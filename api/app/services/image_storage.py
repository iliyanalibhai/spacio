"""Storage backend for uploaded listing images.

Local disk in dev/CI (docker-compose mounts a volume at UPLOAD_DIR so
images survive container restarts); S3 in production once AWS_S3_BUCKET is
set (Phase 5 deploy — see docs/DOCUMENTATION.md §5). The two are switched
on `settings.s3_configured` so the upload router doesn't need to know which
backend is active, and existing local-disk behavior (and its tests) is
unchanged when S3 isn't configured.
"""

from io import BytesIO

import boto3
from PIL import Image

from app.core.config import settings
from app.core.paths import UPLOAD_DIR

_CONTENT_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png"}


def save_image(image: Image.Image, image_format: str, filename: str) -> str:
    """Persists an already-decoded, re-encoded image and returns its public URL."""
    if settings.s3_configured:
        return _save_to_s3(image, image_format, filename)
    return _save_to_disk(image, image_format, filename)


def _save_to_disk(image: Image.Image, image_format: str, filename: str) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    image.save(UPLOAD_DIR / filename, format=image_format)
    return f"/uploads/{filename}"


def _save_to_s3(image: Image.Image, image_format: str, filename: str) -> str:
    buffer = BytesIO()
    image.save(buffer, format=image_format)
    key = f"listings/{filename}"
    boto3.client("s3", region_name=settings.aws_region).put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=buffer.getvalue(),
        ContentType=_CONTENT_TYPES[image_format],
    )
    return f"https://{settings.s3_bucket}.s3.{settings.aws_region}.amazonaws.com/{key}"
