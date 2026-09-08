"""Bill review API: every bill the sync surfaced, with include/exclude decisions.

  GET  /api/bills/review                 list (filterable)
  GET  /api/bills/review/stats           counts by confidence / decision
  GET  /api/bills/review/{id}            single bill
  POST /api/bills/review/{id}/decision   INCLUDED | EXCLUDED | PENDING
  POST /api/bills/review/bulk-decision   same decision for several ids

Decisions take effect on the map immediately: the map reads the same table.
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.legislation import Bill, AUTO_INCLUDE_CONFIDENCE
from app.schemas.legislation import BillOut

router = APIRouter(prefix="/api/bills/review", tags=["bill-review"])

VALID_DECISIONS = {"PENDING", "INCLUDED", "EXCLUDED"}


class DecisionRequest(BaseModel):
    decision: str
    note: Optional[str] = None
    reviewed_by: Optional[str] = "api_user"


class BulkDecisionRequest(BaseModel):
    ids: List[int]
    decision: str
    note: Optional[str] = None
    reviewed_by: Optional[str] = "api_user"


def _check_decision(value: str) -> str:
    d = (value or "").upper()
    if d not in VALID_DECISIONS:
        raise HTTPException(status_code=400, detail=f"decision must be one of {sorted(VALID_DECISIONS)}")
    return d


@router.get("", response_model=List[BillOut])
def list_bills(
    db: Session = Depends(get_db),
    state_code: Optional[str] = Query(None),
    confidence: Optional[str] = Query(None, pattern="^(HIGH|MEDIUM|LOW)$"),
    decision: Optional[str] = Query(None, pattern="^(PENDING|INCLUDED|EXCLUDED)$"),
    flag_reason: Optional[str] = Query(None),
    included: Optional[bool] = Query(None, description="Filter by effective inclusion"),
    stage: Optional[str] = Query(None, pattern="^(passed|debated|introduced|failed)$"),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    q = db.query(Bill)
    if state_code:
        q = q.filter(Bill.state_code == state_code.upper())
    if confidence:
        q = q.filter(Bill.match_confidence == confidence)
    if decision:
        q = q.filter(Bill.decision == decision)
    if flag_reason:
        q = q.filter(Bill.flag_reason == flag_reason)
    if stage:
        q = q.filter(Bill.bill_stage == stage)
    if included is not None:
        # effective inclusion is decision-or-confidence; express it in SQL so
        # limit/offset stay correct.
        from sqlalchemy import or_, and_
        if included:
            q = q.filter(or_(Bill.decision == "INCLUDED",
                             and_(Bill.decision == "PENDING", Bill.match_confidence.in_(AUTO_INCLUDE_CONFIDENCE))))
        else:
            q = q.filter(or_(Bill.decision == "EXCLUDED",
                             and_(Bill.decision == "PENDING", Bill.match_confidence.notin_(AUTO_INCLUDE_CONFIDENCE))))
    return q.order_by(Bill.last_seen.desc(), Bill.id.desc()).offset(offset).limit(limit).all()


@router.get("/stats")
def review_stats(db: Session = Depends(get_db), state_code: Optional[str] = None):
    from sqlalchemy import func
    q = db.query(Bill.match_confidence, Bill.decision, func.count(Bill.id))
    if state_code:
        q = q.filter(Bill.state_code == state_code.upper())
    rows = q.group_by(Bill.match_confidence, Bill.decision).all()

    by_conf = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    by_decision = {"PENDING": 0, "INCLUDED": 0, "EXCLUDED": 0}
    total = on_map = 0
    for conf, dec, n in rows:
        total += n
        if conf in by_conf:
            by_conf[conf] += n
        if dec in by_decision:
            by_decision[dec] += n
        if dec == "INCLUDED" or (dec == "PENDING" and conf in AUTO_INCLUDE_CONFIDENCE):
            on_map += n
    return {
        "total": total,
        "by_confidence": by_conf,
        "by_decision": by_decision,
        "needs_review": by_decision["PENDING"],
        "effective_on_map": on_map,
    }


@router.get("/{bill_id}", response_model=BillOut)
def get_bill(bill_id: int, db: Session = Depends(get_db)):
    bill = db.get(Bill, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    return bill


@router.post("/{bill_id}/decision", response_model=BillOut)
def set_decision(bill_id: int, request: DecisionRequest, db: Session = Depends(get_db)):
    decision = _check_decision(request.decision)
    bill = db.get(Bill, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    bill.decision = decision
    bill.decision_note = request.note
    bill.reviewed_by = request.reviewed_by
    bill.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(bill)
    return bill


@router.post("/bulk-decision")
def set_bulk_decision(request: BulkDecisionRequest, db: Session = Depends(get_db)):
    decision = _check_decision(request.decision)
    bills = db.query(Bill).filter(Bill.id.in_(request.ids)).all()
    now = datetime.utcnow()
    for b in bills:
        b.decision = decision
        b.decision_note = request.note
        b.reviewed_by = request.reviewed_by
        b.reviewed_at = now
    db.commit()
    return {"status": "success", "updated": len(bills), "decision": decision}
