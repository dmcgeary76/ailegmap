from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from app.models.legislation import RegulatoryStance, Maturity, GuidanceType, ResearchStatus


class BillBrief(BaseModel):
    """What the map and state detail need about a bill."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    legiscan_bill_id: int
    bill_number: Optional[str]
    bill_title: Optional[str]
    bill_url: Optional[str]
    bill_text_url: Optional[str] = None
    bill_status: Optional[str]
    bill_stage: Optional[str]
    last_action: Optional[str] = None
    last_action_date: Optional[str]
    match_confidence: Optional[str]
    decision: str
    effective_included: bool
    is_resolution: bool = False


class BillOut(BillBrief):
    """Full review-queue row."""
    state_code: str
    description: Optional[str] = None
    flag_reason: Optional[str] = None
    superseded_by: Optional[int] = None
    ai_mentions: Optional[int] = None
    ai_in_heading: Optional[bool] = None
    definition_only: Optional[bool] = None
    text_words: Optional[int] = None
    subjects: Optional[list] = None
    status_date: Optional[str]
    relevance_score: Optional[int]
    flag_reason: Optional[str]
    matched_ai_terms: Optional[list]
    matched_edu_terms: Optional[list]
    decision_note: Optional[str]
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    first_seen: Optional[datetime]
    last_seen: Optional[datetime]


class LocalActionOut(BaseModel):
    """One notable sub-state action, with its derived status."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    state_code: str
    jurisdiction: str
    jurisdiction_type: str
    action_type: str
    direction: int
    applies_to: Optional[str] = None
    grade_band: Optional[str] = None
    authority: Optional[str] = None
    lifecycle: str
    effective_from: Optional[str] = None
    effective_until: Optional[str] = None
    enrollment: Optional[int] = None
    summary: str
    notes: Optional[str] = None
    sources: List[str] = []
    status: str                               # proposed | active | expired | rescinded (derived)


class ProfileFields(BaseModel):
    research_status: ResearchStatus = ResearchStatus.NOT_RESEARCHED
    guidance_exists: bool = False
    guidance_type: GuidanceType = GuidanceType.NONE
    guidance_issued_by: Optional[str] = None
    guidance_issued_date: Optional[datetime] = None
    guidance_url: Optional[str] = None
    guidance_core_principles: List[str] = []
    regulatory_stance: RegulatoryStance = RegulatoryStance.ABSENT
    maturity: Maturity = Maturity.NASCENT
    key_focus_areas: List[str] = []
    unique_context: Optional[str] = None
    notes: Optional[str] = None
    sources: List[str] = []


class StateSummary(ProfileFields):
    """One entry per jurisdiction for the map."""
    model_config = ConfigDict(from_attributes=True)

    state_code: str
    state_name: str
    last_updated: Optional[datetime] = None
    legislation_stage: Optional[str]          # passed | debated | introduced | failed | None
    headline_bill: Optional[BillBrief]
    bill_counts: Dict[str, Any]
    local_signal: Dict[str, Any]              # count/active/leaning/score/latest/headline (derived)


class StateDetail(StateSummary):
    bills: List[BillBrief]                    # included bills, headline first
    local_actions: List[LocalActionOut]       # active first, then largest / newest


class StateProfileUpdate(BaseModel):
    """Editable researched fields. Anything omitted is left alone."""
    research_status: Optional[ResearchStatus] = None
    guidance_exists: Optional[bool] = None
    guidance_type: Optional[GuidanceType] = None
    guidance_issued_by: Optional[str] = None
    guidance_issued_date: Optional[datetime] = None
    guidance_url: Optional[str] = None
    guidance_core_principles: Optional[List[str]] = None
    regulatory_stance: Optional[RegulatoryStance] = None
    maturity: Optional[Maturity] = None
    key_focus_areas: Optional[List[str]] = None
    unique_context: Optional[str] = None
    notes: Optional[str] = None
    sources: Optional[List[str]] = None


class StatusChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    state_code: str
    bill_number: Optional[str]
    bill_title: Optional[str]
    old_status: Optional[str]
    new_status: Optional[str]
    new_stage: Optional[str]
    changed_at: datetime


class DashboardSummary(BaseModel):
    jurisdictions: int
    states_with_included_bills: int
    states_by_legislation_stage: Dict[str, int]   # passed/debated/introduced/failed/none
    states_researched: int
    states_with_guidance: int
    states_by_stance: Dict[str, int]              # researched states only
    bills: Dict[str, int]                         # total/included/pending/excluded
    local_actions: Dict[str, int]                 # total/active/states + by_leaning
    states_by_local_leaning: Dict[str, int]       # restrictive/permissive/mixed/none
    last_sync: Optional[datetime]
    recent_status_changes: List[StatusChangeOut]
