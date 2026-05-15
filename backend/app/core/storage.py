"""
Supabase Storage client.
FIX ISSUE-02:
- Uses supabase_service_role_key for server-side operations
- Persistent httpx.AsyncClient with connection pooling
"""

import uuid

import httpx
import structlog

from app.core.config import get_settings

settings = get_settings()
log = structlog.get_logger()

BUCKET_NAME = "imports"
# Connection pool: max 10 connections, 30s timeout
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    """Singleton httpx client with connection pooling."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _http_client


def _storage_url(path: str) -> str:
    return f"{settings.supabase_url}/storage/v1/object/{BUCKET_NAME}/{path}"


def _headers(use_service_role: bool = True) -> dict:
    """
    FIX ISSUE-02: server operations use service_role_key, not anon_key.
    service_role bypasses RLS — safe for server-to-server operations.
    """
    key = settings.supabase_service_role_key if use_service_role else settings.supabase_anon_key
    return {
        "Authorization": f"Bearer {key}",
        "apikey": key,
    }


async def upload_file(
    shop_id: uuid.UUID,
    filename: str,
    file_bytes: bytes,
    content_type: str = "text/csv",
) -> str:
    """
    Upload file to Supabase Storage.
    Returns path: uploads/{shop_id}/{uuid}.{ext}
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "csv"
    path = f"uploads/{shop_id}/{uuid.uuid4()}.{ext}"

    client = _get_http_client()
    response = await client.post(
        _storage_url(path),
        content=file_bytes,
        headers={
            **_headers(use_service_role=True),
            "Content-Type": content_type,
            "x-upsert": "false",
        },
    )
    response.raise_for_status()
    log.info("storage.upload_complete", path=path, size_bytes=len(file_bytes))
    return path


async def download_file(path: str) -> bytes:
    """Download file from Supabase Storage for ARQ worker processing."""
    client = _get_http_client()
    response = await client.get(
        _storage_url(path),
        headers=_headers(use_service_role=True),
    )
    response.raise_for_status()
    log.info("storage.download_complete", path=path, size_bytes=len(response.content))
    return response.content


async def delete_file(path: str) -> None:
    client = _get_http_client()
    response = await client.delete(
        _storage_url(path),
        headers=_headers(use_service_role=True),
    )
    response.raise_for_status()
    log.info("storage.delete_complete", path=path)


async def close_client() -> None:
    """Call on app shutdown to close persistent client."""
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None
