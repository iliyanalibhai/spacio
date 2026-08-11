"""Filesystem paths shared between the app and startup code.

Centralized here so the directory the upload router writes to and the
directory main.py mounts as static files can never diverge again — that
divergence (api/app/uploads vs api/uploads) is exactly what made every
uploaded image 404 in the v1 prototype.
"""

from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = API_ROOT / "uploads"
IMAGES_DIR = API_ROOT / "images"
