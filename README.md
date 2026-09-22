# Graph user context

This repository contains a tenant sync job and a protected user-context API for Microsoft Entra and Microsoft Graph.

## What it does

1. A background sync job reads tenant directory data with application permissions and writes normalized user documents to Azure AI Search.
2. A FastAPI app validates an access token for its own audience, exchanges it with MSAL OBO, and returns the signed-in user's live context.

The two paths are intentionally separate. Manager relationships are organizational metadata, not document authorization.

See [docs/architecture.md](docs/architecture.md) for a compact architecture view.
See [docs/production-readiness.md](docs/production-readiness.md) for the prioritized next-step checklist.

## Current scope

Included:
- tenant-wide Graph sync for users and relationships
- manager and direct-report mapping
- membership retrieval, including optional directory-role and administrative-unit enrichment
- delta sync with removal handling via `@removed`
- Azure AI Search indexing and index provisioning
- protected OBO API with audience validation and delegated Graph access
- typed configuration and unit tests

Not a core requirement yet:
- production Azure deployment templates
- full live-tenant validation in a real environment
- advanced telemetry, alerting, and audit dashboards
- document-level authorization beyond separate Search access control

## Quick start

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Use client secrets only for local testing. In Azure, prefer managed identity or a certificate.

## Synchronizer

```powershell
$env:AZURE_TENANT_ID = "tenant-id"
$env:AZURE_CLIENT_ID = "application-id"
$env:AZURE_CREDENTIAL_MODE = "client_secret"
$env:AZURE_CLIENT_SECRET = "local-only-secret"
$env:AZURE_SEARCH_ENDPOINT = "https://service.search.windows.net"
python .\graph_user_export.py --full
```

Create or validate the Search index first:

```powershell
python .\scripts\provision_search_index.py
```

The sync job follows Graph pagination, retries throttling and transient failures, and stores the delta state used for incremental runs.

## OBO API

Set the required settings from `.env.example` and run:

```powershell
uvicorn obo_api:app --host 127.0.0.1 --port 8000
```

Endpoints:
- `GET /health`
- `GET /ready`
- protected `GET /api/user-context`

## Production gaps to close next

The highest-value remaining work is not new app logic; it is operational maturity:

- live validation against a real tenant
- Azure deployment scaffolding
- RBAC and secret configuration review for production
- Application Insights and structured sync health metrics
- alerting for Graph throttling, failed syncs, or Search write issues
- admin reporting for drift, missing memberships, and orphaned relationships

## Quality checks

```powershell
ruff format .
ruff check .
mypy
pytest
```

Integration tests are skipped unless `RUN_INTEGRATION_TESTS=1` and a configured test tenant is available.

## Privacy and security

This export includes directory metadata and may include guests, disabled users, memberships, and reporting relationships. Protect the output, restrict Search access, avoid exposing unnecessary fields to LLMs, and enforce any document-level authorization separately from org hierarchy.

## Migration note

The old scripts remain as compatibility entry points. The real implementation lives under `src/graph_context`, separated by configuration, Graph access, Search sync, jobs, and API code.