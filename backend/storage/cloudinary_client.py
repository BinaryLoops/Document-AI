"""Cloudinary upload helpers for the FastAPI backend."""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any, Dict

import cloudinary
import cloudinary.uploader


_REQUIRED_VARS = (
    "CLOUDINARY_CLOUD_NAME",
    "CLOUDINARY_API_KEY",
    "CLOUDINARY_API_SECRET",
)


def validate_cloudinary_config() -> None:
    """Raise a clear error when Cloudinary configuration is incomplete."""
    missing = [name for name in _REQUIRED_VARS if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "Missing required Cloudinary environment variable(s): "
            + ", ".join(missing)
        )

    cloudinary.config(
        cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
        api_key=os.environ["CLOUDINARY_API_KEY"],
        api_secret=os.environ["CLOUDINARY_API_SECRET"],
        secure=True,
    )


def upload_bytes(content: bytes, *, public_id: str, filename: str) -> Dict[str, Any]:
    """Upload bytes directly to Cloudinary without creating a temp file."""
    validate_cloudinary_config()
    resource_type = "image" if Path(filename).suffix.lower() in {
        ".jpg", ".jpeg", ".png"
    } else "raw"
    result = cloudinary.uploader.upload(
        io.BytesIO(content),
        public_id=public_id,
        folder="documind",
        resource_type=resource_type,
        use_filename=False,
        unique_filename=False,
        context={"original_filename": filename},
    )
    file_format = result.get("format") or Path(filename).suffix.lower().lstrip(".")
    return {
        "fileUrl": result["secure_url"],
        "publicId": result["public_id"],
        "format": file_format,
        "bytes": result.get("bytes", len(content)),
        "resourceType": result.get("resource_type", "raw"),
    }


def delete_file(public_id: str, *, resource_type: str = "raw") -> Dict[str, Any]:
    """Delete an uploaded Cloudinary asset by public ID."""
    validate_cloudinary_config()
    return cloudinary.uploader.destroy(
        public_id,
        resource_type=resource_type,
        invalidate=True,
    )
