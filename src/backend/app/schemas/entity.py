"""Entity Domain Contracts and Subtypes."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class EntityType(str, Enum):
    """Supported entity categories for criminal network analysis."""

    PERSON = "PERSON"
    PHONE = "PHONE"
    VEHICLE = "VEHICLE"
    LOCATION = "LOCATION"
    ORGANIZATION = "ORGANIZATION"
    ACCOUNT = "ACCOUNT"


class Entity(BaseModel):
    """Base Entity domain contract."""

    model_config = ConfigDict(extra="forbid")

    entity_id: str = Field(..., description="Stable URN entity identifier e.g. urn:entity:person:001")
    entity_type: EntityType = Field(..., description="Category of entity")
    canonical_name: str = Field(..., description="Primary display or canonical name")
    aliases: List[str] = Field(default_factory=list, description="Known alternate names or aliases")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Flexible domain attributes")
    source_record_ids: List[str] = Field(default_factory=list, description="Source records referencing this entity")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update timestamp")



class PersonEntity(Entity):
    """Person entity subtype."""

    full_name: str = Field(..., description="Full legal name")
    dob: Optional[str] = Field(None, description="Date of birth in YYYY-MM-DD format")
    gender: Optional[str] = Field(None, description="Gender indicator")
    national_id: Optional[str] = Field(None, description="Normalized National Identification Number")


class PhoneEntity(Entity):
    """Phone entity subtype."""

    phone_number: str = Field(..., description="E.164 normalized phone number e.g. +91-9900000101")
    carrier: Optional[str] = Field(None, description="Telecom carrier name")
    imei: Optional[str] = Field(None, description="Device IMEI number")
    imsi: Optional[str] = Field(None, description="SIM IMSI number")


class VehicleEntity(Entity):
    """Vehicle entity subtype."""

    registration_number: str = Field(..., description="Normalized vehicle registration plate")
    make: Optional[str] = Field(None, description="Vehicle manufacturer")
    model: Optional[str] = Field(None, description="Vehicle model name")
    color: Optional[str] = Field(None, description="Vehicle primary color")
    vin: Optional[str] = Field(None, description="Vehicle Identification Number")


class LocationEntity(Entity):
    """Location entity subtype."""

    address: str = Field(..., description="Physical address text")
    city: Optional[str] = Field(None, description="City name")
    state: Optional[str] = Field(None, description="State / province name")
    latitude: Optional[float] = Field(None, description="Geographic latitude coordinate")
    longitude: Optional[float] = Field(None, description="Geographic longitude coordinate")
    location_type: Optional[str] = Field(None, description="Location classification e.g. HOTEL, HIDE OUT, TOLL_BOOTH")


class OrganizationEntity(Entity):
    """Organization / Firm entity subtype."""

    org_name: str = Field(..., description="Organization registered name")
    registration_id: Optional[str] = Field(None, description="Business registration number")
    org_type: Optional[str] = Field(None, description="Type of organization e.g. SHELL_COMPANY, LOGISTICS")


class AccountEntity(Entity):
    """Financial account entity subtype."""

    account_number: str = Field(..., description="Bank account number")
    bank_name: Optional[str] = Field(None, description="Financial institution name")
    ifsc_code: Optional[str] = Field(None, description="IFSC / Branch routing code")
    account_type: Optional[str] = Field(None, description="Account classification e.g. SAVINGS, CURRENT")
