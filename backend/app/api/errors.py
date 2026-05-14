"""
Global exception handlers for FastAPI.
All errors return consistent JSON shape:
{"error": {"code": "SNAKE_CASE", "message": "Vietnamese user-friendly text"}}
"""
import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse

log = structlog.get_logger()


def _capture_sentry(exc: Exception) -> None:
    """Send exception to Sentry if SDK is initialized — no-op otherwise."""
    try:
        import sentry_sdk
        sentry_sdk.capture_exception(exc)
    except Exception:
        pass


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> ORJSONResponse:
        log.warning("api.validation_error", path=request.url.path, errors=exc.errors())
        return ORJSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Dữ liệu không hợp lệ.",
                    "detail": exc.errors(),
                }
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(
        request: Request, exc: ValueError
    ) -> ORJSONResponse:
        # F-03: log full error internally, return safe Vietnamese message to client
        log.error("api.value_error", path=request.url.path, error=str(exc))
        _capture_sentry(exc)
        _SAFE_MESSAGES: dict[str, str] = {
            "AI budget exceeded":  "Đã đạt giới hạn phân tích AI tháng này. Liên hệ hỗ trợ nếu cần.",
            "AI call failed":      "Tính năng AI tạm thời không khả dụng. Vui lòng thử lại sau.",
            "budget exceeded":     "Đã đạt giới hạn phân tích AI tháng này.",
        }
        msg_vi = next(
            (v for k, v in _SAFE_MESSAGES.items() if k.lower() in str(exc).lower()),
            "Dữ liệu không hợp lệ.",
        )
        return ORJSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": "BAD_REQUEST",
                    "message": msg_vi,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> ORJSONResponse:
        log.exception("api.unhandled_exception", path=request.url.path, error=str(exc))
        _capture_sentry(exc)
        return ORJSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Đã xảy ra lỗi. Vui lòng thử lại sau.",
                }
            },
        )
