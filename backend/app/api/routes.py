"""State-level API: the map's read model plus profile editing."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session, selectinload

from app import derive
from app.database import get_db
from app.models.legislation import (
    StateProfile, Bill, BillStatusChange, SyncRun, LocalAction, JURISDICTIONS,
    RegulatoryStance, ResearchStatus, STAGE_RANK,
)
from app.schemas.legislation import (
    StateSummary, StateDetail, StateProfileUpdate, DashboardSummary, StatusChangeOut, BillBrief,
    LocalActionOut,
)

router = APIRouter(prefix="/api", tags=["states"])


def _ensure_all_profiles(db: Session) -> List[StateProfile]:
    """Every jurisdiction gets a profile row, so the map never has holes."""
    existing = {p.state_code: p for p in db.query(StateProfile).all()}
    missing = [code for code in JURISDICTIONS if code not in existing]
    if missing:
        for code in missing:
            p = StateProfile(state_code=code, state_name=JURISDICTIONS[code])
            db.add(p)
            existing[code] = p
        db.commit()
    return sorted(existing.values(), key=lambda p: p.state_code)


def _actions_by_state(db: Session) -> dict:
    out: dict = {}
    for a in db.query(LocalAction).all():
        out.setdefault(a.state_code, []).append(a)
    return out


def _action_out(a: LocalAction) -> LocalActionOut:
    return LocalActionOut(**{c.name: getattr(a, c.name) for c in LocalAction.__table__.columns
                             if c.name != "added_at"}, status=derive.action_status(a))


def _summary(profile: StateProfile, bills: List[Bill], actions: List[LocalAction] = ()) -> dict:
    head = derive.headline_bill(bills)
    return {
        **{c.name: getattr(profile, c.name) for c in StateProfile.__table__.columns if c.name != "id"},
        "legislation_stage": derive.legislation_stage(bills),
        "headline_bill": BillBrief.model_validate(head) if head else None,
        "bill_counts": derive.review_counts(bills),
        "local_signal": derive.local_signal(actions),
    }


@router.get("/states", response_model=List[StateSummary])
def list_states(
    db: Session = Depends(get_db),
    stance: Optional[RegulatoryStance] = Query(None, description="Researched states with this stance"),
    legislation_stage: Optional[str] = Query(None, pattern="^(passed|debated|introduced|failed|none)$"),
):
    profiles = _ensure_all_profiles(db)
    bills_by_state: dict = {}
    for b in db.query(Bill).all():
        bills_by_state.setdefault(b.state_code, []).append(b)
    actions_by_state = _actions_by_state(db)

    out = []
    for p in profiles:
        s = _summary(p, bills_by_state.get(p.state_code, []), actions_by_state.get(p.state_code, []))
        if stance and not (p.research_status == ResearchStatus.RESEARCHED and p.regulatory_stance == stance):
            continue
        if legislation_stage and (s["legislation_stage"] or "none") != legislation_stage:
            continue
        out.append(s)
    return out


def _get_or_create_profile(db: Session, code: str) -> StateProfile:
    profile = db.query(StateProfile).filter(StateProfile.state_code == code).first()
    if not profile:
        if code not in JURISDICTIONS:
            raise HTTPException(status_code=404, detail=f"Unknown jurisdiction {code}")
        profile = StateProfile(state_code=code, state_name=JURISDICTIONS[code])
        db.add(profile)
        db.commit()
    return profile


@router.get("/states/{state_code}", response_model=StateDetail)
def get_state(state_code: str, db: Session = Depends(get_db)):
    code = state_code.upper()
    profile = _get_or_create_profile(db, code)
    bills = db.query(Bill).filter(Bill.state_code == code).all()
    actions = db.query(LocalAction).filter(LocalAction.state_code == code).all()
    s = _summary(profile, bills, actions)
    s["bills"] = [BillBrief.model_validate(b) for b in derive.included_bills(bills)]
    s["local_actions"] = [_action_out(a) for a in derive.sort_actions(actions)]
    return s


@router.get("/local-actions", response_model=List[LocalActionOut])
def list_local_actions(
    db: Session = Depends(get_db),
    state_code: Optional[str] = Query(None, min_length=2, max_length=2),
    status: Optional[str] = Query(None, pattern="^(proposed|active|expired|rescinded)$"),
):
    """Every curated local action, newest first. Edit data/local_actions/<ST>.json and re-seed to change."""
    q = db.query(LocalAction)
    if state_code:
        q = q.filter(LocalAction.state_code == state_code.upper())
    rows = [_action_out(a) for a in q.all()]
    if status:
        rows = [r for r in rows if r.status == status]
    return sorted(rows, key=lambda r: r.effective_from or "", reverse=True)


@router.put("/states/{state_code}", response_model=StateDetail)
def update_profile(state_code: str, update: StateProfileUpdate, db: Session = Depends(get_db)):
    code = state_code.upper()
    profile = _get_or_create_profile(db, code)
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    profile.last_updated = datetime.utcnow()
    db.commit()
    return get_state(code, db)


def build_dashboard_summary(db: Session) -> DashboardSummary:
    """The dashboard's numbers. Shared by the live endpoint and ``app.export``
    so the static build shows exactly what the API would."""
    profiles = _ensure_all_profiles(db)
    bills = db.query(Bill).all()
    by_state: dict = {}
    for b in bills:
        by_state.setdefault(b.state_code, []).append(b)

    stage_counts = {s: 0 for s in STAGE_RANK}
    stage_counts["none"] = 0
    with_included = 0
    for p in profiles:
        stage = derive.legislation_stage(by_state.get(p.state_code, []))
        stage_counts[stage or "none"] += 1
        if stage:
            with_included += 1

    researched = [p for p in profiles if p.research_status == ResearchStatus.RESEARCHED]
    stance_counts = {s.value: 0 for s in RegulatoryStance}
    for p in researched:
        stance_counts[p.regulatory_stance.value] += 1

    bill_counts = derive.review_counts(bills)

    actions_by_state = _actions_by_state(db)
    leaning_counts = {"restrictive": 0, "permissive": 0, "mixed": 0, "none": 0}
    for p in profiles:
        leaning_counts[derive.local_signal(actions_by_state.get(p.state_code, []))["leaning"] or "none"] += 1
    all_actions = [a for rows in actions_by_state.values() for a in rows]

    last_run = db.query(SyncRun).filter(SyncRun.finished_at.isnot(None)) \
        .order_by(desc(SyncRun.finished_at)).first()

    changes = (
        db.query(BillStatusChange)
        .options(selectinload(BillStatusChange.bill))
        .order_by(desc(BillStatusChange.changed_at))
        .limit(10).all()
    )
    recent = [
        StatusChangeOut(
            state_code=c.bill.state_code, bill_number=c.bill.bill_number,
            bill_title=c.bill.bill_title, old_status=c.old_status,
            new_status=c.new_status, new_stage=c.new_stage, changed_at=c.changed_at,
        )
        for c in changes
    ]

    return DashboardSummary(
        jurisdictions=len(profiles),
        states_with_included_bills=with_included,
        states_by_legislation_stage=stage_counts,
        states_researched=len(researched),
        states_with_guidance=sum(1 for p in profiles if p.guidance_exists),
        states_by_stance=stance_counts,
        bills={
            "total": bill_counts["total"],
            "included": bill_counts["included"],
            "pending": bill_counts["pending"],
            "excluded": bill_counts["manually_excluded"],
        },
        local_actions={
            "total": len(all_actions),
            "active": len(derive.active_actions(all_actions)),
            "states": sum(1 for rows in actions_by_state.values() if rows),
        },
        states_by_local_leaning=leaning_counts,
        last_sync=last_run.finished_at if last_run else None,
        recent_status_changes=recent,
    )


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)):
    return build_dashboard_summary(db)


@router.get("/health")
def health_check():
    return {"status": "ok"}
