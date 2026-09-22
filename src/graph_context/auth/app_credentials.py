"""Application credential selection for background Graph synchronization."""

from __future__ import annotations

from typing import Any

from azure.identity.aio import (
    CertificateCredential,
    ClientSecretCredential,
    DefaultAzureCredential,
    ManagedIdentityCredential,
)

from graph_context.config import CredentialMode, Settings


def build_app_credential(settings: Settings) -> Any:
    """Build the configured async Azure Identity credential."""

    mode = settings.credential_mode
    if mode == CredentialMode.MANAGED_IDENTITY:
        return ManagedIdentityCredential(client_id=settings.client_id)
    if mode == CredentialMode.CERTIFICATE:
        assert settings.certificate_path is not None
        return CertificateCredential(
            tenant_id=settings.tenant_id,
            client_id=settings.client_id,
            certificate_path=settings.certificate_path,
            password=settings.certificate_password.get_secret_value()
            if settings.certificate_password
            else None,
        )
    if mode == CredentialMode.CLIENT_SECRET:
        assert settings.client_secret is not None
        return ClientSecretCredential(
            tenant_id=settings.tenant_id,
            client_id=settings.client_id,
            client_secret=settings.client_secret.get_secret_value(),
        )
    return DefaultAzureCredential(
        exclude_interactive_browser_credential=True,
        managed_identity_client_id=settings.client_id,
    )
