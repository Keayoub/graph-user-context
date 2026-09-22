"""Typed environment configuration for synchronization and OBO services."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CredentialMode(StrEnum):
    DEFAULT = "default"
    MANAGED_IDENTITY = "managed_identity"
    CERTIFICATE = "certificate"
    CLIENT_SECRET = "client_secret"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    tenant_id: str = Field(default="", alias="AZURE_TENANT_ID")
    client_id: str = Field(default="", alias="AZURE_CLIENT_ID")
    credential_mode: CredentialMode = Field(
        default=CredentialMode.DEFAULT, alias="AZURE_CREDENTIAL_MODE"
    )
    client_secret: SecretStr | None = Field(default=None, alias="AZURE_CLIENT_SECRET")
    certificate_path: str | None = Field(default=None, alias="AZURE_CLIENT_CERTIFICATE_PATH")
    certificate_password: SecretStr | None = Field(
        default=None, alias="AZURE_CLIENT_CERTIFICATE_PASSWORD"
    )

    graph_base_url: str = Field(default="https://graph.microsoft.com/v1.0", alias="GRAPH_BASE_URL")
    search_endpoint: str | None = Field(default=None, alias="AZURE_SEARCH_ENDPOINT")
    search_index_name: str = Field(default="organization-users", alias="AZURE_SEARCH_INDEX_NAME")
    concurrency: int = Field(default=8, ge=1, le=64, alias="SYNC_CONCURRENCY")
    batch_size: int = Field(default=500, ge=1, le=1000, alias="SYNC_BATCH_SIZE")
    max_retries: int = Field(default=6, ge=0, le=12, alias="SYNC_MAX_RETRIES")
    request_timeout: float = Field(default=45.0, gt=0, le=300, alias="REQUEST_TIMEOUT_SECONDS")
    sync_memberships: bool = Field(default=True, alias="SYNC_MEMBERSHIPS")
    sync_roles: bool = Field(default=False, alias="SYNC_DIRECTORY_ROLES")
    sync_administrative_units: bool = Field(default=False, alias="SYNC_ADMINISTRATIVE_UNITS")
    delta_link_path: str = Field(default="output/users.delta", alias="DELTA_LINK_PATH")

    obo_tenant_id: str | None = Field(default=None, alias="OBO_TENANT_ID")
    obo_client_id: str | None = Field(default=None, alias="OBO_CLIENT_ID")
    obo_client_secret: SecretStr | None = Field(default=None, alias="OBO_CLIENT_SECRET")
    allowed_tenant: str | None = Field(default=None, alias="ALLOWED_TENANT")
    expected_audience: str | None = Field(default=None, alias="EXPECTED_TOKEN_AUDIENCE")
    api_docs_enabled: bool = Field(default=False, alias="API_DOCS_ENABLED")
    appinsights_connection_string: SecretStr | None = Field(
        default=None, alias="APPLICATIONINSIGHTS_CONNECTION_STRING"
    )
    sync_status_path: str = Field(default="output/sync-status.json", alias="SYNC_STATUS_PATH")
    admin_api_key: SecretStr | None = Field(default=None, alias="ADMIN_API_KEY")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("tenant_id", "client_id")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        return value

    def validate_sync(self) -> None:
        if not self.tenant_id.strip() or not self.client_id.strip():
            raise ValueError("AZURE_TENANT_ID and AZURE_CLIENT_ID are required")
        if self.credential_mode == CredentialMode.CLIENT_SECRET and not self.client_secret:
            raise ValueError("AZURE_CLIENT_SECRET is required for client_secret credential mode")
        if self.credential_mode == CredentialMode.CERTIFICATE and not self.certificate_path:
            raise ValueError("AZURE_CLIENT_CERTIFICATE_PATH is required for certificate mode")
        if self.search_endpoint and not self.search_endpoint.startswith("https://"):
            raise ValueError("AZURE_SEARCH_ENDPOINT must be an https URL")

    def validate_obo(self) -> None:
        missing = [
            name
            for name, value in {
                "OBO_TENANT_ID": self.obo_tenant_id,
                "OBO_CLIENT_ID": self.obo_client_id,
                "OBO_CLIENT_SECRET": self.obo_client_secret,
                "EXPECTED_TOKEN_AUDIENCE": self.expected_audience,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"Missing OBO settings: {', '.join(missing)}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process settings singleton."""

    return Settings()
