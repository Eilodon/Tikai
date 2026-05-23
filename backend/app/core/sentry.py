import structlog

from app.core.config import get_settings

settings = get_settings()
log = structlog.get_logger()

def init_sentry(is_worker: bool = False) -> None:
    """Initialize Sentry for FastAPI or ARQ Worker."""
    if not settings.sentry_dsn:
        log.info("sentry.disabled", reason="DSN not configured")
        return

    import sentry_sdk
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    integrations = [SqlalchemyIntegration()]

    if is_worker:
        try:
            from sentry_sdk.integrations.arq import ArqIntegration
            integrations.append(ArqIntegration())
            log.info("sentry.integration.loaded", name="ArqIntegration")
        except ImportError:
            log.warning("sentry.integration.failed_to_load", name="ArqIntegration")
    else:
        try:
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            integrations.append(FastApiIntegration())
            log.info("sentry.integration.loaded", name="FastApiIntegration")
        except ImportError:
            log.warning("sentry.integration.failed_to_load", name="FastApiIntegration")

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        integrations=integrations,
        traces_sample_rate=0.1 if settings.is_production else 0.0,
        send_default_pii=False,
    )
    log.info("sentry.initialized", is_worker=is_worker)
