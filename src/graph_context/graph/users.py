"""User retrieval and normalization."""

from __future__ import annotations

from collections.abc import Sequence

from graph_context.graph.client import GraphClient
from graph_context.graph.models import UserRecord

USER_FIELDS = [
    "id",
    "accountEnabled",
    "displayName",
    "givenName",
    "surname",
    "userPrincipalName",
    "mail",
    "otherMails",
    "proxyAddresses",
    "userType",
    "createdDateTime",
    "employeeId",
    "employeeType",
    "jobTitle",
    "department",
    "companyName",
    "officeLocation",
    "businessPhones",
    "mobilePhone",
    "preferredLanguage",
    "usageLocation",
    "streetAddress",
    "city",
    "state",
    "postalCode",
    "country",
]
RELATED_FIELDS = [
    "id",
    "displayName",
    "userPrincipalName",
    "mail",
    "jobTitle",
    "department",
    "officeLocation",
]


async def get_users(graph: GraphClient) -> list[UserRecord]:
    url = f"/users?$select={','.join(USER_FIELDS)}&$top=999"
    return [
        UserRecord.model_validate(item) for item in await graph.all_items(url) if item.get("id")
    ]


def normalize_directory_object(item: dict[str, object]) -> dict[str, object]:
    result = dict(item)
    result["type"] = str(item.get("@odata.type", "")).removeprefix("#microsoft.graph.") or None
    return result


def normalize_user_items(items: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    return [normalize_directory_object(item) for item in items if item.get("id")]
