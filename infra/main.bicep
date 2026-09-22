param location string = resourceGroup().location
param tenantId string
param apiIdentityResourceId string
param syncIdentityResourceId string
param environmentName string
param containerImage string
param searchServiceName string
param keyVaultName string
param oboClientSecretName string = 'obo-client-secret'
param adminApiKeySecretName string = 'admin-api-key'
param alertEmail string
param searchIndexName string = 'organization-users'

var logAnalyticsName = '${environmentName}-logs'
var appInsightsName = '${environmentName}-insights'
var apiName = '${environmentName}-api'
var syncJobName = '${environmentName}-sync'
var statusStorageName = take('${toLower(replace(environmentName, '-', ''))}status', 24)
var searchIndexDataContributorRoleId = '8ebe5a00-799e-43f5-93ac-24380c5d7c4d'
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'
var storageBlobDataContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var apiPrincipalId = reference(apiIdentityResourceId, '2023-01-31', 'Full').principalId
var syncPrincipalId = reference(syncIdentityResourceId, '2023-01-31', 'Full').principalId
var apiIdentity = { '${apiIdentityResourceId}': {} }
var syncIdentity = { '${syncIdentityResourceId}': {} }

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

resource statusStorage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: statusStorageName
  location: location
  sku: { name: 'Standard_ZRS' }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}

resource statusContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  name: '${statusStorage.name}/default/operational'
  properties: { publicAccess: 'None' }
}

resource environment 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = { name: keyVaultName }
resource search 'Microsoft.Search/searchServices@2023-11-01' existing = { name: searchServiceName }

resource api 'Microsoft.App/containerApps@2023-05-01' = {
  name: apiName
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: apiIdentity }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
      }
      secrets: [
        {
          name: 'obo-client-secret'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/${oboClientSecretName}'
          identity: apiIdentityResourceId
        }
        {
          name: 'admin-api-key'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/${adminApiKeySecretName}'
          identity: apiIdentityResourceId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: containerImage
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
            { name: 'AZURE_TENANT_ID', value: tenantId }
            { name: 'AZURE_CLIENT_ID', value: reference(apiIdentityResourceId, '2023-01-31', 'Full').clientId }
            { name: 'SYNC_STATUS_BLOB_URL', value: 'https://${statusStorage.name}.blob.${az.environment().suffixes.storage}/operational/sync-status.json' }
            { name: 'OBO_CLIENT_SECRET', secretRef: 'obo-client-secret' }
            { name: 'ADMIN_API_KEY', secretRef: 'admin-api-key' }
            { name: 'API_DOCS_ENABLED', value: 'false' }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
}

resource syncJob 'Microsoft.App/jobs@2023-05-01' = {
  name: syncJobName
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: syncIdentity }
  properties: {
    environmentId: environment.id
    configuration: {
      triggerType: 'Schedule'
      replicaTimeout: 3600
      scheduleTriggerConfig: { cronExpression: '0 * * * *', parallelism: 1 }
    }
    template: {
      containers: [
        {
          name: 'sync'
          image: containerImage
          command: ['python', 'graph_user_export.py', '--full']
          resources: { cpu: 1, memory: '2Gi' }
          env: [
            { name: 'AZURE_TENANT_ID', value: tenantId }
            { name: 'AZURE_CLIENT_ID', value: reference(syncIdentityResourceId, '2023-01-31', 'Full').clientId }
            { name: 'AZURE_CREDENTIAL_MODE', value: 'managed_identity' }
            { name: 'AZURE_SEARCH_ENDPOINT', value: 'https://${search.name}.search.windows.net' }
            { name: 'AZURE_SEARCH_INDEX_NAME', value: searchIndexName }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
            { name: 'SYNC_STATUS_BLOB_URL', value: 'https://${statusStorage.name}.blob.${az.environment().suffixes.storage}/operational/sync-status.json' }
          ]
        }
      ]
    }
  }
}

resource searchRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, syncJob.id, searchIndexDataContributorRoleId)
  scope: search
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataContributorRoleId)
    principalId: syncPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource apiKeyVaultRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, api.id, keyVaultSecretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: apiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource apiStatusStorageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(statusStorage.id, api.id, storageBlobDataContributorRoleId)
  scope: statusStorage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleId)
    principalId: apiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource syncStatusStorageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(statusStorage.id, syncJob.id, storageBlobDataContributorRoleId)
  scope: statusStorage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleId)
    principalId: syncPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: '${environmentName}-alerts'
  location: 'Global'
  properties: {
    groupShortName: 'graphctx'
    enabled: true
    emailReceivers: [{ name: 'operator', emailAddress: alertEmail, useCommonAlertSchema: true }]
  }
}

resource failedSyncAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: '${environmentName}-failed-sync'
  location: location
  properties: {
    severity: 2
    enabled: true
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    scopes: [logAnalytics.id]
    criteria: {
      allOf: [{
        query: 'ContainerAppConsoleLogs_CL | where Log_s has "status=failed"'
        timeAggregation: 'Count'
        operator: 'GreaterThan'
        threshold: 0
      }]
    }
    autoMitigate: true
    actions: { actionGroups: [actionGroup.id] }
  }
}

resource throttlingAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: '${environmentName}-graph-throttling'
  location: location
  properties: {
    severity: 3
    enabled: true
    evaluationFrequency: 'PT15M'
    windowSize: 'PT1H'
    scopes: [logAnalytics.id]
    criteria: {
      allOf: [{
        query: 'ContainerAppConsoleLogs_CL | where Log_s has "graph_throttles=" and Log_s !has "graph_throttles=0"'
        timeAggregation: 'Count'
        operator: 'GreaterThan'
        threshold: 0
      }]
    }
    autoMitigate: true
    actions: { actionGroups: [actionGroup.id] }
  }
}

resource searchWriteAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: '${environmentName}-search-writes'
  location: location
  properties: {
    severity: 2
    enabled: true
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    scopes: [logAnalytics.id]
    criteria: {
      allOf: [{
        query: 'ContainerAppConsoleLogs_CL | where Log_s has "indexing_failures=" and Log_s !has "indexing_failures=0"'
        timeAggregation: 'Count'
        operator: 'GreaterThan'
        threshold: 0
      }]
    }
    autoMitigate: true
    actions: { actionGroups: [actionGroup.id] }
  }
}

output apiName string = api.name
output syncJobName string = syncJob.name
output appInsightsConnectionString string = appInsights.properties.ConnectionString
