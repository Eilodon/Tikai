import pytest
from unittest.mock import patch, MagicMock

def test_sentry_initialization():
    from app.core.sentry import init_sentry

    # Mock settings.sentry_dsn to be set
    with patch("app.core.sentry.settings") as mock_settings:
        mock_settings.sentry_dsn = "https://public@sentry.example.com/1"
        mock_settings.environment = "test"
        mock_settings.is_production = False

        with patch("sentry_sdk.init") as mock_sentry_init:
            init_sentry(is_worker=False)
            mock_sentry_init.assert_called_once()
            
            args, kwargs = mock_sentry_init.call_args
            integrations = kwargs.get("integrations", [])
            integration_names = [type(i).__name__ for i in integrations]
            # Since FastAPI integration is mocked or loaded dynamically
            assert len(integrations) > 0

def test_sentry_initialization_worker():
    from app.core.sentry import init_sentry

    # Mock settings.sentry_dsn to be set
    with patch("app.core.sentry.settings") as mock_settings:
        mock_settings.sentry_dsn = "https://public@sentry.example.com/1"
        mock_settings.environment = "test"
        mock_settings.is_production = False

        with patch("sentry_sdk.init") as mock_sentry_init:
            init_sentry(is_worker=True)
            mock_sentry_init.assert_called_once()
            
            args, kwargs = mock_sentry_init.call_args
            integrations = kwargs.get("integrations", [])
            integration_names = [type(i).__name__ for i in integrations]
            assert len(integrations) > 0
