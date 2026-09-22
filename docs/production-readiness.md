# Production readiness

This checklist covers the work remaining after the core sync and OBO API implementation.

## 1. Validate a real tenant

- [ ] Configure a non-production tenant and Azure AI Search service.
- [ ] Grant only the Graph application and delegated permissions required by the enabled features.
- [ ] Run a full sync and confirm user counts, relationship counts, and Search document counts.
- [ ] Run an incremental sync after changing a user, manager, group membership, and deleted user.
- [ ] Enable directory roles or administrative units only after confirming the required permissions and acceptable data exposure.
- [ ] Run the opt-in integration tests with `RUN_INTEGRATION_TESTS=1`.

**Done when:** full and incremental syncs complete with expected data, removals are reflected in Search, and partial failures are visible in the summary.

## 2. Deploy with managed identity

The initial Container Apps scaffold is in `infra/main.bicep`. It creates the API,
an hourly sync job, Application Insights, Log Analytics, a private status blob,
Search data-plane access, Key Vault secret references, and starter alerts. Replace the values in
`infra/main.parameters.json` and deploy at resource-group scope:

```powershell
az deployment group create --resource-group <resource-group> --template-file infra/main.bicep --parameters @infra/main.parameters.json
```

The template assumes the Search service and Key Vault already exist. Grant the
sync job only `Search Index Data Contributor`; grant the API only `Key Vault
Secrets User` for its OBO secret and admin key.

- [ ] Choose hosting for the API and scheduled sync job.
- [ ] Provision separate identities for the API and sync job.
- [ ] Assign Search data-plane roles to the identities that need them.
- [ ] Store OBO configuration and certificates in Key Vault or the hosting platform's secret store.
- [ ] Disable Search local authentication where the service supports roles-only access.
- [ ] Add deployment configuration without committing tenant IDs, secrets, tokens, or exported directory data.

**Done when:** both workloads start in Azure without client secrets in application settings and can access only their intended resources.

## 3. Add operational visibility

- [ ] Emit structured sync metrics for duration, users processed, deletions, throttling, retries, and failures.
- [ ] Add Application Insights or equivalent request and dependency telemetry to the API.
- [ ] Alert on failed syncs, stale delta state, repeated Graph throttling, and Search write failures.
- [ ] Record correlation IDs and Graph request IDs without logging access tokens or sensitive directory payloads.
- [ ] Define a runbook for replaying a full sync and recovering a lost or invalid delta link.

The API and sync job share the latest redacted sync result through a private Blob
Storage object. The API exposes it at `GET /admin/sync-status` when
`ADMIN_API_KEY` is configured and supplied as `X-Admin-Key`. The response includes
counts for missing memberships and orphaned direct-report relationships; it never
includes directory payloads or delta URLs.

**Done when:** an operator can detect a bad run, identify the failing dependency, and recover without inspecting secrets or raw employee data.

## 4. Govern the indexed data

- [ ] Document which user fields are required by the consuming application or agent.
- [ ] Remove fields that are not needed for the supported scenarios.
- [ ] Define Search retention and deletion behavior for departed users.
- [ ] Model document-level authorization separately from manager and membership relationships.
- [ ] Review Foundry or agent retrieval fields and enforce least-privilege access.
- [ ] Define an owner and review cadence for permissions, retention, and schema changes.

**Done when:** the data owner can explain what is indexed, who can retrieve it, how long it is retained, and how access is enforced.

## Recommended order

1. Real-tenant validation
2. Managed-identity deployment
3. Operational visibility and recovery
4. Data governance and authorization review

The repository is ready for the first step. The remaining items are deployment and operating controls rather than new core Graph features.