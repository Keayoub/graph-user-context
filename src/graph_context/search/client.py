"""Azure AI Search clients using Microsoft Entra RBAC credentials."""

from __future__ import annotations

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient

from graph_context.config import Settings


def build_index_client(settings: Settings) -> SearchIndexClient:
    if not settings.search_endpoint:
        raise ValueError("AZURE_SEARCH_ENDPOINT is required for Search integration")
    return SearchIndexClient(endpoint=settings.search_endpoint, credential=DefaultAzureCredential())


def build_search_client(settings: Settings) -> SearchClient:
    if not settings.search_endpoint:
        raise ValueError("AZURE_SEARCH_ENDPOINT is required for Search integration")
    return SearchClient(
        endpoint=settings.search_endpoint,
        index_name=settings.search_index_name,
        credential=DefaultAzureCredential(),
    )
