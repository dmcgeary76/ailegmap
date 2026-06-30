"""
Manual review queue API endpoints.

Provides interface to review and approve/reject data changes before going live.
All automated data syncs flag items for review first.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models.legislation import StateLegislation, LegislationUpdate

router = APIRouter(prefix="/api/review", tags=["review"])


# Pydantic models for request/response
class ReviewQueueItem(BaseModel):
    """Item pending review."""
    id: int
    state_code: str
    field_name: str
    current_value: Optional[str]
    proposed_value: str
    source: str
    status: str  # PENDING, APPROVED, REJECTED
    reviewed_by: Optional[str]
    review_notes: Optional[str]
    created_at: datetime
    reviewed_at: Optional[datetime]

    class Config:
        from_attributes = True


class ReviewApprovalRequest(BaseModel):
    """Request to approve/reject a review item."""
    status: str  # APPROVED or REJECTED
    notes: Optional[str] = None


@router.get("/queue", response_model=List[ReviewQueueItem])
def get_review_queue(
    db: Session = Depends(get_db),
    status: str = Query("PENDING", regex="^(PENDING|APPROVED|REJECTED)$"),
    state_code: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    """
    Get items in the review queue.

    **Parameters:**
    - status: Filter by status (PENDING, APPROVED, REJECTED)
    - state_code: Filter by state (e.g., CA, TX)
    - limit: Max results (default 50, max 200)

    **Example:**
    ```
    GET /api/review/queue?status=PENDING&state_code=CA
    ```
    """
    query = db.query(LegislationUpdate).filter(
        LegislationUpdate.status == status
    )

    if state_code:
        query = query.filter(LegislationUpdate.state_code == state_code)

    items = query.order_by(LegislationUpdate.created_at.desc()).limit(limit).all()

    return items


@router.get("/queue/{item_id}")
def get_review_item(item_id: int, db: Session = Depends(get_db)):
    """Get a single review queue item."""
    item = db.query(LegislationUpdate).filter(
        LegislationUpdate.id == item_id
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    return item


@router.post("/queue/{item_id}/approve")
def approve_review(
    item_id: int,
    request: ReviewApprovalRequest,
    db: Session = Depends(get_db),
):
    """
    Approve a pending review item and apply the change.

    **Process:**
    1. Update the legislation_updates record status to APPROVED
    2. Apply the change to state_legislation table
    3. Log approval in review_notes

    **Example:**
    ```
    POST /api/review/queue/123/approve
    {
        "status": "APPROVED",
        "notes": "Verified bill status with legislature website"
    }
    ```
    """
    item = db.query(LegislationUpdate).filter(
        LegislationUpdate.id == item_id
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if item.status != "PENDING":
        raise HTTPException(
            status_code=400,
            detail=f"Can only approve PENDING items (current status: {item.status})"
        )

    try:
        # Update review record
        item.status = "APPROVED"
        item.reviewed_by = "api_user"  # TODO: Get from auth context
        item.review_notes = request.notes
        item.reviewed_at = datetime.utcnow()

        # Apply change to state_legislation
        state = db.query(StateLegislation).filter(
            StateLegislation.state_code == item.state_code
        ).first()

        if not state:
            raise HTTPException(
                status_code=404,
                detail=f"State {item.state_code} not found"
            )

        # Set field on state record
        field_name = item.field_name
        if hasattr(state, field_name):
            new_value = item.new_value
            # Handle type conversion
            if field_name in ["graduation_requirement", "teacher_certification_required"]:
                new_value = new_value.lower() == "true"
            setattr(state, field_name, new_value)

        db.commit()

        return {
            "status": "success",
            "message": f"Approved {item.field_name} change for {item.state_code}",
            "item": item,
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/queue/{item_id}/reject")
def reject_review(
    item_id: int,
    request: ReviewApprovalRequest,
    db: Session = Depends(get_db),
):
    """
    Reject a pending review item (discard the change).

    **Example:**
    ```
    POST /api/review/queue/123/reject
    {
        "notes": "Conflicted with manual research - keeping existing value"
    }
    ```
    """
    item = db.query(LegislationUpdate).filter(
        LegislationUpdate.id == item_id
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if item.status != "PENDING":
        raise HTTPException(
            status_code=400,
            detail=f"Can only reject PENDING items (current status: {item.status})"
        )

    try:
        item.status = "REJECTED"
        item.reviewed_by = "api_user"  # TODO: Get from auth context
        item.review_notes = request.notes or "Rejected by user"
        item.reviewed_at = datetime.utcnow()

        db.commit()

        return {
            "status": "success",
            "message": f"Rejected {item.field_name} change for {item.state_code}",
            "item": item,
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue/stats")
def get_queue_stats(db: Session = Depends(get_db)):
    """Get review queue statistics."""
    from sqlalchemy import func

    pending = db.query(func.count(LegislationUpdate.id)).filter(
        LegislationUpdate.status == "PENDING"
    ).scalar() or 0

    approved = db.query(func.count(LegislationUpdate.id)).filter(
        LegislationUpdate.status == "APPROVED"
    ).scalar() or 0

    rejected = db.query(func.count(LegislationUpdate.id)).filter(
        LegislationUpdate.status == "REJECTED"
    ).scalar() or 0

    return {
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
        "total": pending + approved + rejected,
    }


@router.get("/audit/{state_code}")
def get_audit_trail(
    state_code: str,
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
):
    """
    Get full audit trail for a state.

    Shows all changes (approved, rejected, pending) in reverse chronological order.

    **Example:**
    ```
    GET /api/review/audit/CA?limit=50
    ```
    """
    updates = db.query(LegislationUpdate).filter(
        LegislationUpdate.state_code == state_code
    ).order_by(LegislationUpdate.created_at.desc()).limit(limit).all()

    if not updates:
        raise HTTPException(
            status_code=404,
            detail=f"No audit trail found for {state_code}"
        )

    return updates
