from datetime import datetime
from sqlalchemy import (
    Column, String, Text, DateTime, Boolean, Integer, JSON,
    Enum as SQLEnum, ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import relationship
import enum
from app.database import Base


class RegulatoryStance(str, enum.Enum):
    PROHIBIT = "PROHIBIT"
    RESTRICT = "RESTRICT"
    REGULATE = "REGULATE"
    SUPPORT = "SUPPORT"
    MANDATE = "MANDATE"
    ABSENT = "ABSENT"


class Maturity(str, enum.Enum):
    NASCENT = "NASCENT"
    IN_PROGRESS = "IN_PROGRESS"
    ACTIVE = "ACTIVE"
    MATURE = "MATURE"


class GuidanceType(str, enum.Enum):
    MANDATORY = "MANDATORY"
    ADVISORY = "ADVISORY"
    PROPOSED = "PROPOSED"
    NONE = "NONE"


class StateLegislation(Base):
    """State-level AI legislation, guidance, and policy record."""

    __tablename__ = "state_legislation"

    id = Column(Integer, primary_key=True, index=True)
    state_code = Column(String(2), unique=True, index=True, nullable=False)
    state_name = Column(String(50), nullable=False)

    # Legislation
    bill_number = Column(String(50))
    bill_title = Column(String(255))
    bill_url = Column(Text)
    bill_status = Column(String(50))  # Passed, In Committee, Proposed, Pending, Absent
    bill_status_details = Column(Text)
    bill_status_as_of = Column(DateTime)

    # Additional legislation fields (JSON for flexibility)
    additional_bills = Column(JSON, default=[])  # For states with multiple bills
    key_focus_areas = Column(JSON, default=[])  # e.g., ["data_privacy", "academic_integrity"]

    # State Guidance
    guidance_issued_by = Column(String(255))
    guidance_exists = Column(Boolean, default=False)
    guidance_type = Column(SQLEnum(GuidanceType), default=GuidanceType.NONE)
    guidance_core_principles = Column(JSON, default=[])
    guidance_issued_date = Column(DateTime)
    guidance_url = Column(Text)
    guidance_implementation_phase = Column(String(50))  # Planning, Development, Implementation, Rollout, Embedded

    # Implementation Details
    teacher_certification_required = Column(Boolean, default=False)
    graduation_requirement = Column(Boolean, default=False)
    graduation_year = Column(Integer)
    advisory_council = Column(String(255))
    pilot_programs = Column(JSON, default=[])  # List of pilot programs with funding, duration

    # District Reality
    districts_have_policies = Column(Boolean, default=False)
    example_district_actions = Column(JSON, default=[])
    tools_in_use = Column(JSON, default=[])

    # Adoption Metrics
    adoption_metrics = Column(JSON, default={})  # e.g., {"student_usage_pct": 20, "educator_usage_pct": 6}

    # Regional Context
    unique_context = Column(Text)  # Cultural, geographic, or economic context
    stakeholder_requirements = Column(JSON, default=[])

    # Classification
    regulatory_stance = Column(SQLEnum(RegulatoryStance), default=RegulatoryStance.ABSENT)
    maturity = Column(SQLEnum(Maturity), default=Maturity.NASCENT)

    # Metadata
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sources = Column(JSON, default=[])  # List of source URLs
    notes = Column(Text)

    # Relationships
    updates = relationship("LegislationUpdate", back_populates="state_legislation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<StateLegislation(state={self.state_code}, stance={self.regulatory_stance}, maturity={self.maturity})>"


class LegislationUpdate(Base):
    """Audit trail for state legislation changes."""

    __tablename__ = "legislation_updates"

    id = Column(Integer, primary_key=True, index=True)
    state_legislation_id = Column(Integer, ForeignKey("state_legislation.id"), nullable=False)

    # What changed
    field_changed = Column(String(100), nullable=False)  # e.g., "bill_status", "regulatory_stance"
    old_value = Column(Text)
    new_value = Column(Text)

    # Metadata
    changed_at = Column(DateTime, default=datetime.utcnow, index=True)
    changed_by = Column(String(100), default="system")
    change_reason = Column(Text)

    # Relationship
    state_legislation = relationship("StateLegislation", back_populates="updates")

    def __repr__(self):
        return f"<LegislationUpdate(state_id={self.state_legislation_id}, field={self.field_changed}, at={self.changed_at})>"


class BillReviewItem(Base):
    """One row per bill surfaced by the LegiScan sync (any confidence).

    This is a BILL-level curation queue (distinct from the field-level
    `legislation_updates` audit trail). Every discovered bill is recorded with
    its automatic relevance classification, and a human can override whether it
    is included on the map via `decision`. Re-running the sync refreshes the
    bill's metadata/status but never clobbers a manual decision.
    """

    __tablename__ = "bill_review_queue"
    __table_args__ = (
        UniqueConstraint("state_code", "legiscan_bill_id", name="uq_review_state_bill"),
    )

    id = Column(Integer, primary_key=True, index=True)
    state_code = Column(String(2), index=True, nullable=False)
    legiscan_bill_id = Column(Integer, index=True)  # unique per bill across sessions

    # Bill metadata (refreshed each sync)
    bill_number = Column(String(50))
    bill_title = Column(String(500))
    bill_url = Column(Text)
    bill_text_url = Column(Text)
    bill_status = Column(String(50))         # human label, e.g. "Passed"
    bill_stage = Column(String(20))          # introduced | debated | passed | failed
    status_date = Column(String(20))
    last_action = Column(Text)
    last_action_date = Column(String(20))

    # Automatic relevance classification (refreshed each sync)
    relevance_score = Column(Integer, default=0)
    match_confidence = Column(String(10))    # HIGH | MEDIUM | LOW
    auto_decision = Column(String(10))       # INCLUDE | REVIEW (system suggestion)
    flag_reason = Column(String(20))         # noise | higher_ed | review | ""
    matched_ai_terms = Column(JSON, default=[])
    matched_edu_terms = Column(JSON, default=[])

    # Manual override (preserved across syncs)
    decision = Column(String(10), default="PENDING")  # PENDING | INCLUDED | EXCLUDED
    decision_note = Column(Text)
    reviewed_by = Column(String(100))
    reviewed_at = Column(DateTime)

    # Bookkeeping
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def effective_included(self) -> bool:
        """Whether this bill should appear on the map.

        A manual decision wins; otherwise fall back to the auto classification
        (HIGH/MEDIUM are auto-included, LOW is held for review).
        """
        if self.decision == "INCLUDED":
            return True
        if self.decision == "EXCLUDED":
            return False
        return self.match_confidence in ("HIGH", "MEDIUM")

    def __repr__(self):
        return (f"<BillReviewItem(state={self.state_code}, bill={self.bill_number}, "
                f"conf={self.match_confidence}, decision={self.decision})>")
