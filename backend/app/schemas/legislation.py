from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app.models.legislation import RegulatoryStance, Maturity, GuidanceType


class LegislationUpdateResponse(BaseModel):
    id: int
    state_legislation_id: int
    field_changed: str
    old_value: Optional[str]
    new_value: Optional[str]
    changed_at: datetime
    changed_by: str
    change_reason: Optional[str]

    class Config:
        from_attributes = True


class StateLegislationBase(BaseModel):
    state_code: str
    state_name: str
    bill_number: Optional[str] = None
    bill_title: Optional[str] = None
    bill_url: Optional[str] = None
    bill_status: Optional[str] = None
    bill_status_details: Optional[str] = None
    bill_status_as_of: Optional[datetime] = None
    additional_bills: List[Dict[str, Any]] = []
    key_focus_areas: List[str] = []

    guidance_issued_by: Optional[str] = None
    guidance_exists: bool = False
    guidance_type: GuidanceType = GuidanceType.NONE
    guidance_core_principles: List[str] = []
    guidance_issued_date: Optional[datetime] = None
    guidance_url: Optional[str] = None
    guidance_implementation_phase: Optional[str] = None

    teacher_certification_required: bool = False
    graduation_requirement: bool = False
    graduation_year: Optional[int] = None
    advisory_council: Optional[str] = None
    pilot_programs: List[Dict[str, Any]] = []

    districts_have_policies: bool = False
    example_district_actions: List[str] = []
    tools_in_use: List[str] = []

    adoption_metrics: Dict[str, Any] = {}
    unique_context: Optional[str] = None
    stakeholder_requirements: List[str] = []

    regulatory_stance: RegulatoryStance = RegulatoryStance.ABSENT
    maturity: Maturity = Maturity.NASCENT

    sources: List[str] = []
    notes: Optional[str] = None


class StateLegislationCreate(StateLegislationBase):
    pass


class StateLegislationUpdate(BaseModel):
    bill_status: Optional[str] = None
    bill_status_details: Optional[str] = None
    bill_status_as_of: Optional[datetime] = None
    regulatory_stance: Optional[RegulatoryStance] = None
    maturity: Optional[Maturity] = None
    notes: Optional[str] = None
    adoption_metrics: Optional[Dict[str, Any]] = None
    example_district_actions: Optional[List[str]] = None
    sources: Optional[List[str]] = None


class StateLegislationResponse(StateLegislationBase):
    id: int
    last_updated: datetime
    updates: List[LegislationUpdateResponse] = []

    class Config:
        from_attributes = True


class DashboardSummary(BaseModel):
    """Summary statistics for the dashboard."""
    total_states: int
    states_by_stance: Dict[str, int]
    states_by_maturity: Dict[str, int]
    states_with_guidance: int
    states_with_legislation: int
    recent_updates: List[LegislationUpdateResponse]
