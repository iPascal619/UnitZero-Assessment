"""Episode router: list, import CSV."""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from app.database import get_db
from app.models import Episode, Assignment
from app.schemas import EpisodeOut, ImportResult
from app.dependencies import get_current_user, require_role
from app.services.csv_import import import_episodes_from_csv
from app.models import User

router = APIRouter(prefix="/api/episodes", tags=["episodes"])


@router.get("", response_model=list[EpisodeOut])
def list_episodes(
    task_name: str | None = Query(None),
    quality: str | None = Query(None),
    available_only: bool = Query(False, description="Only show unassigned episodes"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List episodes with optional filters. Operators/admins only."""
    if current_user.role not in ("operator", "admin"):
        raise HTTPException(status_code=403, detail="Not authorized")

    query = db.query(Episode)

    if task_name:
        query = query.filter(Episode.task_name == task_name.lower().strip())
    if quality:
        query = query.filter(Episode.quality == quality.lower().strip())
    if available_only:
        # Only episodes not already assigned
        assigned_ids = db.query(Assignment.episode_id).subquery()
        query = query.filter(~Episode.id.in_(assigned_ids))

    episodes = query.order_by(Episode.id).offset(offset).limit(limit).all()

    # Check assignment status for each episode
    assigned_episode_ids = set(
        row[0]
        for row in db.query(Assignment.episode_id)
        .filter(Assignment.episode_id.in_([e.id for e in episodes]))
        .all()
    )

    results = []
    for ep in episodes:
        out = EpisodeOut.model_validate(ep)
        out.is_assigned = ep.id in assigned_episode_ids
        results.append(out)

    return results


@router.get("/task-names", response_model=list[str])
def list_task_names(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return distinct task names for filter dropdowns."""
    rows = db.query(Episode.task_name).distinct().order_by(Episode.task_name).all()
    return [r[0] for r in rows]


@router.post("/import", response_model=ImportResult)
async def import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("operator", "admin")),
):
    """Import episodes from a CSV file. Idempotent — safe to run repeatedly."""
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
    result = import_episodes_from_csv(db, text)
    return ImportResult(**result)
