import pytest

from graph_context.config import CredentialMode, Settings


def test_client_secret_mode_requires_secret() -> None:
    settings = Settings(
        AZURE_TENANT_ID="tenant",
        AZURE_CLIENT_ID="client",
        AZURE_CREDENTIAL_MODE=CredentialMode.CLIENT_SECRET,
    )
    with pytest.raises(ValueError, match="AZURE_CLIENT_SECRET"):
        settings.validate_sync()


def test_obo_settings_validation_lists_missing_values() -> None:
    settings = Settings(AZURE_TENANT_ID="tenant", AZURE_CLIENT_ID="client")
    with pytest.raises(ValueError, match="OBO_TENANT_ID"):
        settings.validate_obo()
