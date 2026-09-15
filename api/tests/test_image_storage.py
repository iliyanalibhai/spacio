"""Tests for app/services/image_storage.py — the local-disk/S3 storage
switch used by POST /listings/upload. See docs/DOCUMENTATION.md §5.
"""

import boto3
from moto import mock_aws
from PIL import Image

from app.core.config import settings
from app.services.image_storage import save_image


def _red_square() -> Image.Image:
    return Image.new("RGB", (10, 10), color="red")


def test_save_image_uses_local_disk_when_s3_not_configured(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "s3_bucket", "")
    monkeypatch.setattr("app.services.image_storage.UPLOAD_DIR", tmp_path)

    url = save_image(_red_square(), "PNG", "photo.png")

    assert url == "/uploads/photo.png"
    assert (tmp_path / "photo.png").exists()


@mock_aws
def test_save_image_uploads_to_s3_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "s3_bucket", "spacio-test-bucket")
    monkeypatch.setattr(settings, "aws_region", "us-east-1")
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="spacio-test-bucket")

    url = save_image(_red_square(), "JPEG", "photo.jpg")

    assert url == "https://spacio-test-bucket.s3.us-east-1.amazonaws.com/listings/photo.jpg"
    stored = boto3.client("s3", region_name="us-east-1").get_object(
        Bucket="spacio-test-bucket", Key="listings/photo.jpg"
    )
    assert stored["ContentType"] == "image/jpeg"
    assert stored["Body"].read()
