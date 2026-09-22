# Graph user context

This repository provides two separate Microsoft Entra and Microsoft Graph
paths:

1. A background synchronizer uses application permissions to normalize tenant
   users, management relationships, and optional memberships into Azure AI
   Search.
2. A protected FastAPI service validates an access token for its own audience,
   exchanges it with MSAL OBO, and returns live context for the signed-in user.

The paths deliberately do not share authorization. A manager relationship is
organizational metadata and never grants access to documents.

See [docs/architecture.md](docs/architecture.md) for the architecture diagram.

## Quick start

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Use client secrets only for local synchronization tests. Use managed identity
or a certificate in Azure. Never commit `.env`, certificates, exported data,
or tokens.

## App registrations

Create two separate single-tenant registrations.

### Background synchronization app

Grant Microsoft Graph **Application** permission `User.Read.All`, then grant
tenant admin consent. This is sufficient for `/users`, direct reports, and
another user's transitive memberships in the implemented default behavior.

Add `Directory.Read.All` only if the tenant requires broader directory object
properties. Add `GroupMember.Read.Hidden` only to read hidden group membership.
Directory roles and administrative units are disabled by default because their
permissions are more sensitive; enable them only after reviewing tenant policy.

Configure `AZURE_CREDENTIAL_MODE` as `managed_identity`, `certificate`,
`client_secret`, or `default`. `default` uses `DefaultAzureCredential` and is
recommended for Azure-hosted workloads with a user-assigned managed identity.

### OBO web API app

Expose `api://<web-api-client-id>/access_as_user` and have the client request a
token for this custom API, not for Microsoft Graph. Configure the known client
application or pre-authorized application as appropriate. Add delegated Graph
permission `User.Read`. Add `User.Read.All` only if the API must read related
properties outside the signed-in user's default profile boundary, and grant
admin consent where required.

The API validates tenant, issuer, audience, signature, expiration, not-before,
and required claims before calling MSAL OBO. It never returns the downstream
Graph token.

## Run the synchronizer

```powershell
$env:AZURE_TENANT_ID = "tenant-id"
$env:AZURE_CLIENT_ID = "application-id"
$env:AZURE_CREDENTIAL_MODE = "client_secret"
$env:AZURE_CLIENT_SECRET = "local-only-secret"
$env:AZURE_SEARCH_ENDPOINT = "https://service.search.windows.net"
python .\graph_user_export.py --full
```

The synchronizer follows `@odata.nextLink`, uses bounded workers, retries 429
with `Retry-After`, retries transient 5xx responses with jitter, and records
partial relationship failures in the summary. After an initial full sync,
omit `--full` to use the saved delta link at `DELTA_LINK_PATH`; Graph delta
responses containing `@removed` are sent as Search deletes.

Create or validate the Search index first:

```powershell
python .\scripts\provision_search_index.py
```

The Search client uses Entra RBAC. Assign the synchronizer identity **Search
Index Data Contributor** and the provisioning identity **Search Service
Contributor**. Disable local authentication for a production roles-only
service.

## Run the OBO API

Set `OBO_TENANT_ID`, `OBO_CLIENT_ID`, `OBO_CLIENT_SECRET`, and
`EXPECTED_TOKEN_AUDIENCE`, then run:

```powershell
uvicorn obo_api:app --host 127.0.0.1 --port 8000
```

Endpoints are `GET /health`, `GET /ready`, and protected
`GET /api/user-context`. Set `API_DOCS_ENABLED=true` only for development to
expose `/docs` and `/redoc`.

## Quality checks

```powershell
ruff format .
ruff check .
mypy
pytest
docker build --tag graph-user-context:local .
```

Integration tests are skipped unless `RUN_INTEGRATION_TESTS=1` and a separately
configured test tenant are provided. Unit tests mock external calls.

## Foundry IQ

After indexing, add the Azure AI Search organization index as a Foundry IQ
knowledge source using the Search service endpoint and index name. Configure
the Foundry identity with the required Search data-plane reader role. Keep
retrieved fields limited to what the agent needs and do not use hierarchy as a
document access-control rule. Any document-level authorization must be modeled
and enforced separately.

## Troubleshooting

- **401 or consent errors:** confirm the client requested the custom API scope,
  the API audience matches `EXPECTED_TOKEN_AUDIENCE`, and both the OBO app's
  Graph delegated permissions and admin consent are present.
- **Graph 403:** inspect the exact endpoint permission. Memberships can return
  limited-information directory objects under least privilege; optional
  failures are returned in API metadata and sync summaries.
- **Graph 429/5xx:** lower `SYNC_CONCURRENCY`, increase retry settings, and
  inspect request IDs in structured logs.
- **Search indexing failures:** verify Entra RBAC, index field names, service
  tier, and that batches are within the configured limit. Per-document failures
  are counted in the synchronization summary.

## Privacy and retention

The export contains employee directory information and may include guests,
disabled users, memberships, and reporting relationships. Restrict access to
the output and Search index, define retention with the tenant owner, avoid
sending unnecessary fields to an LLM, and delete stale documents during delta
processing.

## Migration notes

The original `graph_user_export.py` and `obo_api.py` implementations are now
thin compatibility entry points. Shared behavior lives under
`src/graph_context`, separated into configuration, authentication, Graph,
Search, jobs, and API modules. Existing local commands continue to work while
the package layout supports dependency injection and unit testing.