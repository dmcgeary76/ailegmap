"""Data model.

Two kinds of data live here and they are deliberately kept apart:

* ``bills`` -- everything the LegiScan sync discovers, one row per bill, with
  the automatic relevance call and an overridable human decision. This is the
  ONLY place bills are stored. A state's headline bill and bill list are
  derived from it at read time (see ``app/derive.py``), so a reviewer's
  include/exclude decision is what the map shows -- there is no second copy
  to drift out of sync.

* ``state_profiles`` -- the manually researched layer: state education agency
  guidance, regulatory stance, context, sources. The sync creates an empty
  profile for each jurisdiction it touches but never edits the researched
  fields.

* ``local_actions`` -- notable *non-legislative* moves by districts, cities,
  counties and regional bodies (a moratorium, a policy, a procurement). One
  row per action, never one row per district: this is a curated layer loaded
  from ``data/local_actions/<STATE>.json`` under a written inclusion rule, so
  it stays at tens of rows nationally. Status (active / expired / ...) and a
  per-state "local signal" are derived at read time (``app/derive.py``).
"""
from datetime import datetime
import enum
import re

from sqlalchemy import (
    Column, String, Text, DateTime, Boolean, Integer, Float, JSON,
    Enum as SQLEnum, ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import relationship

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


class ResearchStatus(str, enum.Enum):
    """Whether a human has researched this jurisdiction's guidance/stance yet.

    Stance and maturity mean nothing until this is RESEARCHED -- the UI shows
    "not yet assessed" rather than "no legislation" for unresearched states.
    """
    NOT_RESEARCHED = "NOT_RESEARCHED"
    RESEARCHED = "RESEARCHED"


# Map color-coding derives from the strongest stage among a state's included
# bills. Higher = stronger.
STAGE_RANK = {"passed": 4, "debated": 3, "introduced": 2, "failed": 1}

# Resolutions (HR, SR, HCR, SJR, AJR, memorials, Maine "Resolves"...) never
# become law, so an adopted one must not paint a state "Passed into law".
# They stay on the map as bills a reader should see, but derive.py skips them
# when computing a state's stage. LegiScan's bill_type isn't stored (yet), so
# this reads the bill number and, for Maine, the title.
_RESOLUTION_NUMBER = re.compile(r"^(?:[HSAL]|HC|SC|AC|LC|HJ|SJ|AJ|LJ|HCJ|SCJ)?(?:R|M|JM|CM)\s?\d", re.I)
_RESOLUTION_TITLE = re.compile(
    r"^\s*(?:resolve\b|(?:a\s+)?(?:house|senate|assembly|concurrent|joint)?\s*resolution\b)", re.I)


def is_resolution(bill_number: str, title: str = "") -> bool:
    n = (bill_number or "").strip()
    if _RESOLUTION_NUMBER.match(n):
        return True
    # Maine numbers bills and resolves alike as LD; Rhode Island numbers House
    # resolutions like bills (H8345, "HOUSE RESOLUTION CREATING ..."). The
    # title tells.
    if _RESOLUTION_TITLE.match(title or ""):
        return True
    return False

# Which automatic confidence levels put a PENDING bill on the map without a
# human looking at it. Only HIGH: the title names both AI and education.
# MEDIUM ("education in the title, AI somewhere in the body") turned out to be
# mostly digital-citizenship / cyberbullying / CS-curriculum bills that mention
# AI once in a definitions list -- 0 of 126 had an AI term in the title
# (2026-09-04 audit), so they wait in the review queue like LOW does.
AUTO_INCLUDE_CONFIDENCE = ("HIGH",)

JURISDICTIONS = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "District of Columbia",
    "GU": "Guam", "PR": "Puerto Rico", "VI": "US Virgin Islands",
}

# LegiScan has no coverage for these (confirmed 2026-07-01: "Invalid state").
# Their profiles are maintained by hand only.
LEGISCAN_UNSUPPORTED = {"GU", "PR", "VI"}


class StateProfile(Base):
    """Manually researched state-level layer: guidance, stance, context."""

    __tablename__ = "state_profiles"

    id = Column(Integer, primary_key=True)
    state_code = Column(String(2), unique=True, index=True, nullable=False)
    state_name = Column(String(50), nullable=False)
    research_status = Column(SQLEnum(ResearchStatus), default=ResearchStatus.NOT_RESEARCHED,
                             nullable=False)

    # State education agency guidance
    guidance_exists = Column(Boolean, default=False, nullable=False)
    guidance_type = Column(SQLEnum(GuidanceType), default=GuidanceType.NONE, nullable=False)
    guidance_issued_by = Column(String(255))
    guidance_issued_date = Column(DateTime)
    guidance_url = Column(Text)
    guidance_core_principles = Column(JSON, default=list)

    # Classification (meaningful only when research_status == RESEARCHED)
    regulatory_stance = Column(SQLEnum(RegulatoryStance), default=RegulatoryStance.ABSENT,
                               nullable=False)
    maturity = Column(SQLEnum(Maturity), default=Maturity.NASCENT, nullable=False)
    key_focus_areas = Column(JSON, default=list)

    # Narrative
    unique_context = Column(Text)
    notes = Column(Text)
    sources = Column(JSON, default=list)

    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    bills = relationship("Bill", back_populates="state",
                         primaryjoin="StateProfile.state_code == foreign(Bill.state_code)",
                         viewonly=True)

    def __repr__(self):
        return f"<StateProfile {self.state_code} {self.research_status.value}>"


class Bill(Base):
    """One row per bill the LegiScan sync surfaced, at any confidence."""

    __tablename__ = "bills"
    __table_args__ = (
        UniqueConstraint("state_code", "legiscan_bill_id", name="uq_bill_state_legiscan"),
    )

    id = Column(Integer, primary_key=True)
    state_code = Column(String(2), index=True, nullable=False)
    legiscan_bill_id = Column(Integer, index=True, nullable=False)

    # Bill metadata (refreshed each sync)
    bill_number = Column(String(50))
    bill_title = Column(Text)
    description = Column(Text)          # getBill description, when fetched
    subjects = Column(JSON, default=list)  # getBill subject tags, when fetched
    bill_url = Column(Text)
    bill_text_url = Column(Text)
    bill_status = Column(String(50))    # human label, e.g. "Passed"
    bill_stage = Column(String(20))     # introduced | debated | passed | failed
    status_date = Column(String(20))
    last_action = Column(Text)
    last_action_date = Column(String(20))
    change_hash = Column(String(64))    # LegiScan change_hash; skip getBill when unchanged

    # Automatic relevance classification (refreshed each sync)
    relevance_score = Column(Integer, default=0)
    match_confidence = Column(String(10))   # HIGH | MEDIUM | LOW
    flag_reason = Column(String(20))        # noise | higher_ed | review | ""
    matched_ai_terms = Column(JSON, default=list)
    matched_edu_terms = Column(JSON, default=list)

    # Text-density score (app/sync/text_scorer.py). The text itself is never
    # stored; text_hash lets a re-run skip unchanged documents.
    text_doc_id = Column(Integer)
    text_hash = Column(String(64))
    text_mime = Column(Integer)          # LegiScan mime_id (1 HTML, 2 PDF, 6 docx ...)
    text_words = Column(Integer)         # None = document fetched but unreadable
    ai_mentions = Column(Integer)
    ai_in_heading = Column(Boolean)
    ai_density = Column(Float)           # mentions per 1,000 words
    definition_only = Column(Boolean)
    text_scored_at = Column(DateTime)

    # Carry-over duplicate: LegiScan gives a bill a fresh id when a two-year
    # session rolls into its second year, so the same bill can exist twice.
    # The older copy points at the newer one and stays off the map.
    superseded_by = Column(Integer, index=True)   # legiscan_bill_id of the newer copy

    # Human decision (preserved across syncs)
    decision = Column(String(10), default="PENDING", nullable=False)  # PENDING | INCLUDED | EXCLUDED
    decision_note = Column(Text)
    reviewed_by = Column(String(100))
    reviewed_at = Column(DateTime)

    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)

    state = relationship("StateProfile", back_populates="bills",
                         primaryjoin="foreign(Bill.state_code) == StateProfile.state_code",
                         viewonly=True)
    status_changes = relationship("BillStatusChange", back_populates="bill",
                                  cascade="all, delete-orphan",
                                  order_by="BillStatusChange.changed_at.desc()")

    @property
    def is_resolution(self) -> bool:
        return is_resolution(self.bill_number, self.bill_title)

    @property
    def effective_included(self) -> bool:
        """Whether this bill appears on the map: manual decision wins, else AUTO_INCLUDE_CONFIDENCE."""
        if self.decision == "INCLUDED":
            return True
        if self.decision == "EXCLUDED":
            return False
        if self.superseded_by:
            return False
        return self.match_confidence in AUTO_INCLUDE_CONFIDENCE

    def __repr__(self):
        return f"<Bill {self.state_code} {self.bill_number} {self.match_confidence}/{self.decision}>"


class BillStatusChange(Base):
    """A bill moved stage (e.g. Introduced -> Passed) between two syncs."""

    __tablename__ = "bill_status_changes"

    id = Column(Integer, primary_key=True)
    bill_id = Column(Integer, ForeignKey("bills.id", ondelete="CASCADE"), nullable=False, index=True)
    old_status = Column(String(50))
    new_status = Column(String(50))
    old_stage = Column(String(20))
    new_stage = Column(String(20))
    changed_at = Column(DateTime, default=datetime.utcnow, index=True)

    bill = relationship("Bill", back_populates="status_changes")


class SyncRun(Base):
    """One row per sync invocation, so the UI can say when data was last refreshed."""

    __tablename__ = "sync_runs"

    id = Column(Integer, primary_key=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime)
    scope = Column(String(20))       # "all" or a state code
    stats = Column(JSON, default=dict)


# ---------------------------------------------------------------------------
# Local (sub-state) actions
# ---------------------------------------------------------------------------

ACTION_TYPES = ("MORATORIUM", "RESTRICT", "PERMIT", "ADOPT", "GUIDANCE", "PROCUREMENT")
JURISDICTION_TYPES = ("district", "city", "county", "region", "consortium")
LIFECYCLES = ("proposed", "adopted", "rescinded")
APPLIES_TO = ("students", "staff", "both")


class LocalAction(Base):
    """A notable non-legislative action by a sub-state body.

    ``direction`` is the sentiment proxy: what the body *did*, on a scale from
    -2 (prohibit) through 0 (neutral, e.g. guidance that neither restricts nor
    encourages) to +2 (embrace / mandate use). ``lifecycle`` is what a human
    knows (proposed / adopted / rescinded); whether it is currently in force is
    computed from the dates, never edited by hand.
    """

    __tablename__ = "local_actions"

    id = Column(Integer, primary_key=True)
    state_code = Column(String(2), index=True, nullable=False)
    jurisdiction = Column(String(200), nullable=False)          # "New York City Public Schools"
    jurisdiction_type = Column(String(20), nullable=False)      # JURISDICTION_TYPES
    action_type = Column(String(20), nullable=False)            # ACTION_TYPES
    direction = Column(Integer, default=0, nullable=False)      # -2 .. +2
    applies_to = Column(String(10), default="students")         # APPLIES_TO
    grade_band = Column(String(20))                             # "PK-8", "K-12", "9-12"
    authority = Column(String(120))                             # "board vote", "superintendent memo", ...
    lifecycle = Column(String(10), default="adopted", nullable=False)  # LIFECYCLES
    effective_from = Column(String(10))                         # ISO date
    effective_until = Column(String(10))                        # ISO date; None = open-ended
    enrollment = Column(Integer)                                # approximate; weights the state rollup
    summary = Column(Text, nullable=False)
    notes = Column(Text)
    sources = Column(JSON, default=list)
    added_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<LocalAction {self.state_code} {self.jurisdiction} {self.action_type} {self.direction:+d}>"
