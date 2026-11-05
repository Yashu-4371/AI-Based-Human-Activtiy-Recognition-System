from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.utils.email_validation import clean_optional_email


class CaregiverBase(BaseModel):
    full_name: str
    phone: str
    email: Optional[str] = None
    relationship_to_patient: Optional[str] = None
    additional_contact_info: Optional[str] = None


class CaregiverCreate(CaregiverBase):
    patient_ids: List[int] = []

    # Validate only on input. CaregiverOut stays lenient so a legacy row with an
    # odd saved address can still be listed (and fixed) instead of breaking the page.
    @field_validator("email", mode="before")
    @classmethod
    def _validate_email(cls, value):
        return clean_optional_email(value)


class CaregiverUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    relationship_to_patient: Optional[str] = None
    additional_contact_info: Optional[str] = None

    @field_validator("email", mode="before")
    @classmethod
    def _validate_email(cls, value):
        return clean_optional_email(value)


class PatientSummary(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class CaregiverOut(CaregiverBase):
    id: int
    created_at: datetime
    patients: List[PatientSummary] = []

    model_config = ConfigDict(from_attributes=True)


class TestEmailOut(BaseModel):
    __test__ = False  # not a pytest class

    sent: bool
    recipient: str  # masked, e.g. "j***@gmail.com"
    message: str
