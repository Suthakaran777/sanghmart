import os
import uuid
from typing import Tuple
import boto3
from botocore.config import Config

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "").strip()
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "").strip()
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "sanghmart-proofs").strip()
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "").strip()

def get_r2_client():
    if not (R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY):
        return None
    endpoint_url = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3.v4")
    )

def upload_screenshot_file(contents: bytes, filename: str, content_type: str = "image/jpeg") -> str:
    """
    Uploads screenshot to Cloudflare R2 if configured, otherwise saves to local disk.
    Returns file_id / URL.
    """
    ext = os.path.splitext(filename)[1] or ".jpg"
    file_id = f"proof_{uuid.uuid4().hex}{ext}"

    r2 = get_r2_client()
    if r2:
        try:
            r2.put_object(
                Bucket=R2_BUCKET_NAME,
                Key=file_id,
                Body=contents,
                ContentType=content_type
            )
            # If public URL is provided, return public URL or file_id
            if R2_PUBLIC_URL:
                clean_base = R2_PUBLIC_URL.rstrip('/')
                return f"{clean_base}/{file_id}"
            return file_id
        except Exception as e:
            print(f"R2 Upload failed, falling back to local disk: {e}")

    # Fallback to local storage
    file_path = os.path.join(UPLOAD_DIR, file_id)
    with open(file_path, "wb") as f:
        f.write(contents)
    return file_id
