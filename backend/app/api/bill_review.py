"""
Bill-level review queue API.

Lets a human evaluate every bill the LegiScan sync surfaced and manually
include or exclude it from the map. The future review UI consumes these
endpoints.

  GET  /api/bills/review              list items (filterable)
  GET  /api/bills/review/stats        counts by confidence / decision
  GET  /api/bills/review/{id}         single item
  POST /api/bills/review/{id}/decision   set INCLUDED / EXCLUDED / PENDING
  POST /api/bills/review/bulk-decision   set decision for several items at once
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models.legislation import BillReviewItem

router = APIRouter(prefix="/api/bills/review", tags=["bill-review"])

VALID_DECISIONS = {"PENDING", "INCLUDED", "EXCLUDED"}


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------

class BillReviewOut(BaseModel):
    id: int
    state_code: str
    legiscan_bill_id: Optional[int]
    bill_number: Optional[str]
    bill_title: Optional[str]
    bill_url: Optional[str]
    bill_status: Optional[str]
    bill_stage: Optional[str]
    status_date: Optional[str]
    last_action_date: Optional[str]
    relevance_score: Optional[int]
    match_confidence: Optional[str]
    auto_decision: Optional[str]
    flag_reason: Optional[str]
    matched_ai_terms: Optional[list]
    matched_edu_terms: Optional[list]
    decision: Optional[str]
    decision_note: Optional[str]
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    effective_included: bool

    class Config:
        from_attributes = True


class DecisionRequest(BaseModel):
    decision: str                       # INCLUDED | EXCLUDED | PENDING
    note: Optional[str] = None
    reviewed_by: Optional[str] = "api_user"


class BulkDecisionRequest(BaseModel):
    ids: List[int]
    decision: str
    note: Optional[str] = None
    reviewed_by: Optional[str] = "api_user"


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

@router.get("", response_model=List[BillReviewOut])
@router.get("/", response_model=List[BillReviewOut])
def list_review_items(
    db: Session = Depends(get_db),
    state_code: Optional[str] = Query(None, description="Filter by state, e.g. CA"),
    confidence: Optional[str] = Query(None, regex="^(HIGH|MEDIUM|LOW)$"),
    decision: Optional[str] = Query(None, regex="^(PENDING|INCLUDED|EXCLUDED)$"),
    flag_reason: Optional[str] = Query(None, description="noise | higher_ed | review"),
    included: Optional[bool] = Query(None, description="Filter by EFFECTIVE inclusion"),
    limit: int = Query(200, ge=1, le=1000),
):
    """List review-queue bills. Defaults to newest-seen first.

    `included` filters on the *effective* decision (manual override or, if none,
    the auto classification) and is applied in Python since it's a derived value.
    """
    q = db.query(BillReviewItem)
    if state_code:
        q = q.filter(BillReviewItem.state_code == state_code.upper())
    if confidence:
        q = q.filter(BillReviewItem.match_confidence == confidence)
    if decision:
        q = q.filter(BillReviewItem.decision == decision)
    if flag_reason:
        q = q.filter(BillReviewItem.flag_reason == flag_reason)

    items = q.order_by(BillReviewItem.last_seen.desc()).limit(limit).all()
    if included is not None:
        items = [it for it in items if it.effective_included == included]
    return items


@router.get("/stats")
def review_stats(db: Session = Depends(get_db),
                 state_code: Optional[str] = None):
    """Counts by confidence and decision (optionally scoped to one state)."""
    q = db.query(BillReviewItem)
    if state_code:
        q = q.filter(BillReviewItem.state_code == state_code.upper())
    items = q.all()

    by_conf = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    by_decision = {"PENDING": 0, "INCLUDED": 0, "EXCLUDED": 0}
    effective_on_map = 0
    for it in items:
        if it.match_confidence in by_conf:
            by_conf[it.match_confidence] += 1
        if it.decision in by_decision:
            by_decision[it.decision] += 1
        if it.effective_included:
            effective_on_map += 1

    return {
        "total": len(items),
        "by_confidence": by_conf,
        "by_decision": by_decision,
        "needs_review": by_decision["PENDING"],  # not yet manually decided
        "effective_on_map": effective_on_map,
    }


@router.get("/{item_id}", response_model=BillReviewOut)
def get_review_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(BillReviewItem).filter(BillReviewItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    return item


@router.post("/{item_id}/decision", response_model=BillReviewOut)
def set_decision(item_id: int, request: DecisionRequest, db: Session = Depends(get_db)):
    """Manually include/exclude a bill (or reset to PENDING to defer to auto)."""
    decision = request.decision.upper()
    if decision not in VALID_DECISIONS:
        raise HTTPException(status_code=400,
                            detail=f"decision must be one of {sorted(VALID_DECISIONS)}")

    item = db.query(BillReviewItem).filter(BillReviewItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")

    item.decision = decision
    item.decision_note = request.note
    item.reviewed_by = request.reviewed_by
    item.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return item


@router.post("/bulk-decision")
def set_bulk_decision(request: BulkDecisionRequest, db: Session = Depends(get_db)):
    """Apply the same decision to several review items at once."""
    decision = request.decision.upper()
    if decision not in VALID_DECISIONS:
        raise HTTPException(status_code=400,
                            detail=f"decision must be one of {sorted(VALID_DECISIONS)}")

    items = db.query(BillReviewItem).filter(BillReviewItem.id.in_(request.ids)).all()
    now = datetime.utcnow()
    for it in items:
        it.decision = decision
        it.decision_note = request.note
        it.reviewed_by = request.reviewed_by
        it.reviewed_at = now
    db.commit()
    return {"status": "success", "updated": len(items), "decision": decision}
