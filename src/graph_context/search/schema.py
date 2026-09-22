"""Azure AI Search schema for normalized organizational users."""

from __future__ import annotations

from azure.search.documents.indexes.models import (
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
)


def organization_index(name: str) -> SearchIndex:
    string = SearchFieldDataType.String
    string_collection = SearchFieldDataType.Collection(string)
    fields = [
        SimpleField(name="id", type=string, key=True, filterable=True, retrievable=True),
        SearchableField(name="displayName", type=string, filterable=True, retrievable=True),
        SearchableField(name="userPrincipalName", type=string, filterable=True, retrievable=True),
        SearchableField(name="mail", type=string, filterable=True, retrievable=True),
        SearchableField(
            name="jobTitle", type=string, filterable=True, facetable=True, retrievable=True
        ),
        SearchableField(
            name="department", type=string, filterable=True, facetable=True, retrievable=True
        ),
        SearchableField(
            name="companyName", type=string, filterable=True, facetable=True, retrievable=True
        ),
        SearchableField(name="officeLocation", type=string, filterable=True, retrievable=True),
        SearchableField(
            name="city", type=string, filterable=True, facetable=True, retrievable=True
        ),
        SearchableField(
            name="state", type=string, filterable=True, facetable=True, retrievable=True
        ),
        SearchableField(
            name="country", type=string, filterable=True, facetable=True, retrievable=True
        ),
        SimpleField(name="accountEnabled", type="Edm.Boolean", filterable=True, retrievable=True),
        SimpleField(
            name="userType", type=string, filterable=True, facetable=True, retrievable=True
        ),
        SearchableField(name="managerDisplayName", type=string, filterable=True, retrievable=True),
        SimpleField(name="managerId", type=string, filterable=True, retrievable=True),
        SearchableField(
            name="managerUserPrincipalName", type=string, filterable=True, retrievable=True
        ),
        SearchField(name="directReportIds", type=string_collection, filterable=True),
        SearchField(
            name="membershipIds",
            type=string_collection,
            filterable=True,
            facetable=True,
        ),
        SearchableField(
            name="membershipDisplayNames",
            type=string_collection,
            filterable=True,
            facetable=True,
        ),
        SimpleField(
            name="synchronizedAt",
            type="Edm.DateTimeOffset",
            filterable=True,
            sortable=True,
            retrievable=True,
        ),
    ]
    semantic = SemanticConfiguration(
        name="organization-semantic",
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="displayName"),
            content_fields=[
                SemanticField(field_name="jobTitle"),
                SemanticField(field_name="department"),
                SemanticField(field_name="companyName"),
                SemanticField(field_name="officeLocation"),
                SemanticField(field_name="membershipDisplayNames"),
            ],
            keywords_fields=[SemanticField(field_name="userPrincipalName")],
        ),
    )
    return SearchIndex(
        name=name, fields=fields, semantic_search=SemanticSearch(configurations=[semantic])
    )
