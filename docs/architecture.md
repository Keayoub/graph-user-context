# Architecture

```mermaid
flowchart LR
    Client[Client application] -->|access token for custom API| OBO[Protected OBO API]
    OBO --> Entra[Microsoft Entra ID]
    Entra -->|delegated Graph token| OBO
    OBO -->|delegated calls| Graph[Microsoft Graph]
    Job[Background synchronization job] -->|application token| Entra
    Job -->|users, relationships, memberships| Graph
    Job -->|mergeOrUpload and deletes| Search[Azure AI Search organization index]
    Search --> IQ[Foundry IQ knowledge base]
```

The two paths have different trust boundaries. The background job is allowed to
read tenant-wide directory data and writes only normalized organizational
documents. The API receives a user-scoped token for its own audience, validates
it locally, then uses OBO to call Graph with that user's delegated permissions.

Manager relationships are organizational metadata, not document authorization.
Search permissions and any document ACL fields must be enforced independently.
