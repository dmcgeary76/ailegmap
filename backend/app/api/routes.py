from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from datetime import datetime

from app.database import get_db
from app.models.legislation import StateLegislation, LegislationUpdate, RegulatoryStance, Maturity
from app.schemas.legislation import (
    StateLegislationCreate,
    StateLegislationResponse,
    StateLegislationUpdate as StateLegislationUpdateSchema,
    DashboardSummary,
    LegislationUpdateResponse,
)

router = APIRouter(prefix="/api", tags=["legislation"])


# Retrieve endpoints

@router.get("/states", response_model=List[StateLegislationResponse])
def get_all_states(
    db: Session = Depends(get_db),
    stance: str = Query(None),
    maturity: str = Query(None),
):
    """Get all state legislation records with optional filtering."""
    query = db.query(StateLegislation)

    if stance:
        query = query.filter(StateLegislation.regulatory_stance == stance)
    if maturity:
        query = query.filter(StateLegislation.maturity == maturity)

    return query.all()


@router.get("/states/{state_code}", response_model=StateLegislationResponse)
def get_state(state_code: str, db: Session = Depends(get_db)):
    """Get legislation record for a specific state."""
    state = db.query(StateLegislation).filter(
        StateLegislation.state_code == state_code.upper()
    ).first()

    if not state:
        raise HTTPException(status_code=404, detail=f"State {state_code} not found")

    return state


@router.get("/dashboard/summary", response_model=DashboardSummary)
def get_dashboard_summary(db: Session = Depends(get_db)):
    """Get dashboard summary statistics."""
    total_states = db.query(StateLegislation).count()

    # Count by stance
    stance_counts = {}
    for stance in RegulatoryStance:
        count = db.query(StateLegislation).filter(
            StateLegislation.regulatory_stance == stance
        ).count()
        stance_counts[stance.value] = count

    # Count by maturity
    maturity_counts = {}
    for mat in Maturity:
        count = db.query(StateLegislation).filter(
            StateLegislation.maturity == mat
        ).count()
        maturity_counts[mat.value] = count

    # States with guidance
    states_with_guidance = db.query(StateLegislation).filter(
        StateLegislation.guidance_exists == True
    ).count()

    # States with legislation
    states_with_legislation = db.query(StateLegislation).filter(
        StateLegislation.bill_number.isnot(None)
    ).count()

    # Recent updates
    recent_updates = db.query(LegislationUpdate).order_by(
        desc(LegislationUpdate.changed_at)
    ).limit(10).all()

    return DashboardSummary(
        total_states=total_states,
        states_by_stance=stance_counts,
        states_by_maturity=maturity_counts,
        states_with_guidance=states_with_guidance,
        states_with_legislation=states_with_legislation,
        recent_updates=recent_updates,
    )


# Create endpoint

@router.post("/states", response_model=StateLegislationResponse)
def create_state_legislation(
    legislation: StateLegislationCreate,
    db: Session = Depends(get_db),
):
    """Create a new state legislation record."""
    # Check if state already exists
    existing = db.query(StateLegislation).filter(
        StateLegislation.state_code == legislation.state_code.upper()
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"State {legislation.state_code} already exists"
        )

    db_legislation = StateLegislation(
        **legislation.model_dump()
    )
    db.add(db_legislation)
    db.commit()
    db.refresh(db_legislation)

    return db_legislation


# Update endpoint

@router.put("/states/{state_code}", response_model=StateLegislationResponse)
def update_state_legislation(
    state_code: str,
    update_data: StateLegislationUpdateSchema,
    db: Session = Depends(get_db),
):
    """Update a state legislation record."""
    state = db.query(StateLegislation).filter(
        StateLegislation.state_code == state_code.upper()
    ).first()

    if not state:
        raise HTTPException(status_code=404, detail=f"State {state_code} not found")

    # Track changes
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        old_value = getattr(state, field)
        if old_value != value:
            # Create audit log entry
            audit = LegislationUpdate(
                state_legislation_id=state.id,
                field_changed=field,
                old_value=str(old_value),
                new_value=str(value),
                changed_at=datetime.utcnow(),
                changed_by="user",
            )
            db.add(audit)

        setattr(state, field, value)

    state.last_updated = datetime.utcnow()
    db.commit()
    db.refresh(state)

    return state


# Health check

@router.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
