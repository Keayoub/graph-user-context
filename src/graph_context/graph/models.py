"""Typed models for normalized Graph directory data."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DirectoryObject(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    display_name: str | None = Field(default=None, alias="displayName")
    user_principal_name: str | None = Field(default=None, alias="userPrincipalName")
    mail: str | None = None
    job_title: str | None = Field(default=None, alias="jobTitle")
    department: str | None = None
    office_location: str | None = Field(default=None, alias="officeLocation")
    object_type: str | None = Field(default=None, alias="type")


class Membership(DirectoryObject):
    object_type: str | None = Field(default=None, alias="type")


class UserRecord(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str
    account_enabled: bool | None = Field(default=None, alias="accountEnabled")
    display_name: str | None = Field(default=None, alias="displayName")
    given_name: str | None = Field(default=None, alias="givenName")
    surname: str | None = None
    user_principal_name: str | None = Field(default=None, alias="userPrincipalName")
    mail: str | None = None
    other_mails: list[str] = Field(default_factory=list, alias="otherMails")
    proxy_addresses: list[str] = Field(default_factory=list, alias="proxyAddresses")
    user_type: str | None = Field(default=None, alias="userType")
    created_date_time: datetime | None = Field(default=None, alias="createdDateTime")
    employee_id: str | None = Field(default=None, alias="employeeId")
    employee_type: str | None = Field(default=None, alias="employeeType")
    job_title: str | None = Field(default=None, alias="jobTitle")
    department: str | None = None
    company_name: str | None = Field(default=None, alias="companyName")
    office_location: str | None = Field(default=None, alias="officeLocation")
    business_phones: list[str] = Field(default_factory=list, alias="businessPhones")
    mobile_phone: str | None = Field(default=None, alias="mobilePhone")
    preferred_language: str | None = Field(default=None, alias="preferredLanguage")
    usage_location: str | None = Field(default=None, alias="usageLocation")
    street_address: str | None = Field(default=None, alias="streetAddress")
    city: str | None = None
    state: str | None = None
    postal_code: str | None = Field(default=None, alias="postalCode")
    country: str | None = None
    manager: DirectoryObject | None = None
    direct_reports: list[DirectoryObject] = Field(default_factory=list, alias="directReports")
    memberships: list[Membership] = Field(default_factory=list)
    optional_failures: list[str] = Field(default_factory=list, alias="optionalFailures")

    def to_search_document(self, synchronized_at: datetime) -> dict[str, Any]:
        document = self.model_dump(by_alias=True, exclude_none=True)
        manager = document.pop("manager", None) or {}
        reports = document.pop("directReports", [])
        memberships = document.pop("memberships", [])
        document.update(
            {
                "id": self.id,
                "managerId": manager.get("id"),
                "managerDisplayName": manager.get("displayName"),
                "managerUserPrincipalName": manager.get("userPrincipalName"),
                "directReportIds": [item.get("id") for item in reports if item.get("id")],
                "membershipIds": [item.get("id") for item in memberships if item.get("id")],
                "membershipDisplayNames": [
                    item.get("displayName") for item in memberships if item.get("displayName")
                ],
                "synchronizedAt": synchronized_at.isoformat(),
            }
        )
        return document


class SyncSummary(BaseModel):
    users_seen: int = 0
    users_indexed: int = 0
    users_deleted: int = 0
    relationship_failures: int = 0
    membership_failures: int = 0
    indexing_failures: int = 0
    delta_link: str | None = None
