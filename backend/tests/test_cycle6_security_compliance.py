import inspect

import pytest
from fastapi import HTTPException


def test_admin_secret_uses_constant_time_compare_and_rate_limit():
    from app.api.v1 import admin

    source = inspect.getsource(admin)

    assert "hmac.compare_digest" in source
    assert '@limiter.limit("10/hour")' in source


def test_cogs_template_sanitizes_csv_formula_cells():
    from app.api.v1.cogs import _safe_csv_cell

    assert _safe_csv_cell('=HYPERLINK("https://evil.test")').startswith("'=")
    assert _safe_csv_cell("+cmd").startswith("'+")
    assert _safe_csv_cell("@SUM(A1:A2)").startswith("'@")
    assert _safe_csv_cell("SKU-001") == "SKU-001"


def test_cogs_bulk_import_has_upload_size_cap():
    from app.api.v1 import cogs

    source = inspect.getsource(cogs.bulk_import_cogs)

    assert "MAX_COGS_UPLOAD_BYTES" in source
    assert "FILE_TOO_LARGE" in source
    assert "await file.read(MAX_COGS_UPLOAD_BYTES + 1)" in source


def test_frontend_csp_allows_configured_backend_origin():
    source = open("../frontend/next.config.ts", encoding="utf-8").read()

    assert "NEXT_PUBLIC_API_URL" in source
    assert "new URL(raw).origin" in source
    assert "connect-src ${connectSrc.join" in source


@pytest.mark.parametrize("candidate", ["", "wrong"])
def test_admin_missing_or_wrong_key_forbidden(candidate, monkeypatch):
    from app.api.v1 import admin

    class Request:
        headers = {"X-Admin-Key": candidate}

    monkeypatch.setattr(admin.settings, "admin_secret", "correct-secret")

    with pytest.raises(HTTPException) as exc:
        admin._check_admin_key(Request())

    assert exc.value.status_code == 403
