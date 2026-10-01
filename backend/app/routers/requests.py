"""Request router: CRUD, status transitions, assignment management."""

import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import User, Request, Assignment, Episode, StatusHistory
from app.schemas import (
    RequestCreate,
    RequestOut,
    StatusTransition,
    AssignmentCreate,
    AssignmentOut,
    StatusHistoryOut,
    EpisodeOut,
)
from app.dependencies import get_current_user, require_role
from app.events import event_manager

router = APIRouter(prefix="/api/requests", tags=["requests"])

# ── Valid status transitions and who can perform them ─────────────────────────
TRANSITIONS = {
    ("submitted", "in_progress"): {"operator", "admin"},
    ("in_progress", "delivered"): {"operator", "admin"},
    ("delivered", "accepted"): {"client"},
    ("delivered", "rejected"): {"client"},
    ("rejected", "in_progress"): {"operator", "admin"},
}


def _request_to_out(req: Request, db: Session) -> RequestOut:
    """Convert a Request model to RequestOut with assignment count."""
    assigned_count = (
        db.query(Assignment).filter(Assignment.request_id == req.id).count()
    )
    return RequestOut(
        id=req.id,
        client_id=req.client_id,
        client_username=req.client.username if req.client else None,
        task_name=req.task_name,
        episodes_requested=req.episodes_requested,
        deadline=req.deadline,
        notes=req.notes,
        status=req.status,
        created_at=req.created_at,
        updated_at=req.updated_at,
        assigned_count=assigned_count,
    )


@router.get("", response_model=list[RequestOut])
def list_requests(
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List requests. Clients see only their own; operators/admins see all."""
    query = db.query(Request).options(joinedload(Request.client))

    if current_user.role == "client":
        query = query.filter(Request.client_id == current_user.id)

    if status_filter:
        query = query.filter(Request.status == status_filter)

    requests = query.order_by(Request.created_at.desc()).all()
    return [_request_to_out(r, db) for r in requests]


@router.post("", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    body: RequestCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("client")),
):
    """Create a new dataset request (client only)."""
    req = Request(
        client_id=current_user.id,
        task_name=body.task_name,
        episodes_requested=body.episodes_requested,
        deadline=body.deadline,
        notes=body.notes,
        status="submitted",
    )
    db.add(req)
    db.flush()

    # Record initial status
    history = StatusHistory(
        request_id=req.id,
        from_status=None,
        to_status="submitted",
        changed_by=current_user.id,
    )
    db.add(history)
    db.commit()
    db.refresh(req)

    # SSE event
    background_tasks.add_task(
        event_manager.publish,
        "request_created",
        {"request_id": req.id, "task_name": req.task_name, "status": req.status},
    )

    return _request_to_out(req, db)


@router.get("/{request_id}", response_model=RequestOut)
def get_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single request by ID."""
    req = (
        db.query(Request)
        .options(joinedload(Request.client))
        .filter(Request.id == request_id)
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    # Clients can only see their own
    if current_user.role == "client" and req.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return _request_to_out(req, db)


@router.patch("/{request_id}/status", response_model=RequestOut)
def transition_status(
    request_id: int,
    body: StatusTransition,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Move a request to a new status. Enforces valid transitions and roles."""
    req = (
        db.query(Request)
        .options(joinedload(Request.client))
        .filter(Request.id == request_id)
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    transition_key = (req.status, body.status)

    # Check valid transition
    allowed_roles = TRANSITIONS.get(transition_key)
    if allowed_roles is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition: {req.status} → {body.status}",
        )

    # Check role authorization
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{current_user.role}' cannot perform transition {req.status} → {body.status}",
        )

    # Client can only transition their own requests
    if current_user.role == "client" and req.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Check delivery prerequisite: must have enough episodes assigned
    if body.status == "delivered":
        assigned_count = (
            db.query(Assignment).filter(Assignment.request_id == req.id).count()
        )
        if assigned_count < req.episodes_requested:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot deliver: {assigned_count}/{req.episodes_requested} episodes assigned",
            )

    # Perform transition
    old_status = req.status
    req.status = body.status

    history = StatusHistory(
        request_id=req.id,
        from_status=old_status,
        to_status=body.status,
        changed_by=current_user.id,
        notes=body.notes,
    )
    db.add(history)
    db.commit()
    db.refresh(req)

    # SSE event
    background_tasks.add_task(
        event_manager.publish,
        "status_changed",
        {
            "request_id": req.id,
            "from_status": old_status,
            "to_status": body.status,
            "changed_by": current_user.username,
        },
    )

    return _request_to_out(req, db)


@router.get("/{request_id}/history", response_model=list[StatusHistoryOut])
def get_status_history(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the status change history for a request."""
    req = db.query(Request).filter(Request.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if current_user.role == "client" and req.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    history = (
        db.query(StatusHistory)
        .filter(StatusHistory.request_id == request_id)
        .order_by(StatusHistory.changed_at)
        .all()
    )
    results = []
    for h in history:
        out = StatusHistoryOut.model_validate(h)
        out.username = h.user.username if h.user else None
        results.append(out)
    return results


# ── Assignments ───────────────────────────────────────────────────────────────

@router.get("/{request_id}/assignments", response_model=list[AssignmentOut])
def list_assignments(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List episodes assigned to a request."""
    req = db.query(Request).filter(Request.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if current_user.role == "client" and req.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    assignments = (
        db.query(Assignment)
        .options(joinedload(Assignment.episode))
        .filter(Assignment.request_id == request_id)
        .order_by(Assignment.assigned_at)
        .all()
    )

    results = []
    for a in assignments:
        out = AssignmentOut.model_validate(a)
        if a.episode:
            ep_out = EpisodeOut.model_validate(a.episode)
            ep_out.is_assigned = True
            out.episode = ep_out
        results.append(out)
    return results


@router.post(
    "/{request_id}/assignments",
    response_model=list[AssignmentOut],
    status_code=status.HTTP_201_CREATED,
)
def assign_episodes(
    request_id: int,
    body: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("operator", "admin")),
):
    """Assign episodes to a request. Enforces quality and uniqueness rules."""
    req = db.query(Request).filter(Request.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if req.status not in ("submitted", "in_progress", "rejected"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot assign episodes to a request in '{req.status}' status",
        )

    # Validate episodes
    episodes = db.query(Episode).filter(Episode.id.in_(body.episode_ids)).all()
    if len(episodes) != len(body.episode_ids):
        found_ids = {e.id for e in episodes}
        missing = [eid for eid in body.episode_ids if eid not in found_ids]
        raise HTTPException(
            status_code=404, detail=f"Episodes not found: {missing}"
        )

    errors = []
    for ep in episodes:
        # Check quality
        if ep.quality not in ("good", "usable"):
            errors.append(
                f"Episode {ep.episode_id} has quality '{ep.quality}' (must be good or usable)"
            )
        # Check not already assigned
        existing = (
            db.query(Assignment).filter(Assignment.episode_id == ep.id).first()
        )
        if existing:
            errors.append(
                f"Episode {ep.episode_id} is already assigned to request #{existing.request_id}"
            )

    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    # Create assignments
    created = []
    for ep in episodes:
        assignment = Assignment(
            episode_id=ep.id,
            request_id=req.id,
            assigned_by=current_user.id,
        )
        db.add(assignment)
        db.flush()
        db.refresh(assignment)
        out = AssignmentOut.model_validate(assignment)
        ep_out = EpisodeOut.model_validate(ep)
        ep_out.is_assigned = True
        out.episode = ep_out
        created.append(out)

    db.commit()
    return created


@router.delete("/{request_id}/assignments/{assignment_id}", status_code=204)
def remove_assignment(
    request_id: int,
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("operator", "admin")),
):
    """Remove an episode assignment from a request."""
    assignment = (
        db.query(Assignment)
        .filter(Assignment.id == assignment_id, Assignment.request_id == request_id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    req = db.query(Request).filter(Request.id == request_id).first()
    if req and req.status in ("delivered", "accepted"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot remove assignments from a '{req.status}' request",
        )

    db.delete(assignment)
    db.commit()
