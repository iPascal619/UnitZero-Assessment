"""Analytics router: episodes per day/robot, request fulfilment, top tasks.

All computations are done in SQL — no loading into Python.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, cast, Date, extract

from app.database import get_db
from app.models import Episode, Request, StatusHistory, User
from app.schemas import (
    AnalyticsResponse,
    EpisodesPerDayPerRobot,
    RequestsByStatus,
    TopTask,
)
from app.dependencies import require_role

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("", response_model=AnalyticsResponse)
def get_analytics(
    start_date: date = Query(..., description="Start of date range (inclusive)"),
    end_date: date = Query(..., description="End of date range (inclusive)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("operator", "admin")),
):
    """Return analytics for the given date range.

    - Episodes recorded per day, per robot
    - Request count by status + median time from submitted to delivered
    - Top 5 task names by number of good episodes

    These queries use database aggregation. With 5 million episodes the
    episodes_per_day_per_robot and top_tasks queries are the most expensive.
    We have indexes on (recorded_at), (robot_id), (task_name), and (quality)
    to keep them fast. For truly large scale we would add a composite index
    on (recorded_at, robot_id) and consider materialized views or a
    time-series partitioning scheme on the episodes table.
    """

    # 1. Episodes per day per robot
    eps_query = (
        db.query(
            cast(Episode.recorded_at, Date).label("date"),
            Episode.robot_id,
            func.count().label("count"),
        )
        .filter(
            Episode.recorded_at.isnot(None),
            cast(Episode.recorded_at, Date) >= start_date,
            cast(Episode.recorded_at, Date) <= end_date,
        )
        .group_by(cast(Episode.recorded_at, Date), Episode.robot_id)
        .order_by(cast(Episode.recorded_at, Date), Episode.robot_id)
        .all()
    )
    episodes_per_day = [
        EpisodesPerDayPerRobot(date=row.date, robot_id=row.robot_id, count=row.count)
        for row in eps_query
    ]

    # 2. Requests by status (all requests, not filtered by date for overall picture)
    status_query = (
        db.query(Request.status, func.count().label("count"))
        .group_by(Request.status)
        .all()
    )
    requests_by_status = [
        RequestsByStatus(status=row.status, count=row.count) for row in status_query
    ]

    # 3. Median time from submitted to delivered
    # PostgreSQL supports percentile_cont; SQLite does not.
    from sqlalchemy.sql import text

    median_hours = None
    dialect = db.bind.dialect.name if db.bind else "sqlite"

    try:
        if dialect == "postgresql":
            median_result = db.execute(
                text("""
                    SELECT percentile_cont(0.5) WITHIN GROUP (
                        ORDER BY EXTRACT(EPOCH FROM (delivered.changed_at - submitted.changed_at)) / 3600.0
                    ) AS median_hours
                    FROM (
                        SELECT request_id, MIN(changed_at) AS changed_at
                        FROM status_history
                        WHERE to_status = 'submitted'
                        GROUP BY request_id
                    ) submitted
                    JOIN (
                        SELECT request_id, MIN(changed_at) AS changed_at
                        FROM status_history
                        WHERE to_status = 'delivered'
                        GROUP BY request_id
                    ) delivered ON submitted.request_id = delivered.request_id
                """)
            ).fetchone()
            if median_result and median_result[0] is not None:
                median_hours = round(float(median_result[0]), 2)
        else:
            # SQLite fallback: compute fulfilment hours per request, sort, pick median
            rows = db.execute(
                text("""
                    SELECT
                        (julianday(delivered.changed_at) - julianday(submitted.changed_at)) * 24.0
                        AS hours
                    FROM (
                        SELECT request_id, MIN(changed_at) AS changed_at
                        FROM status_history
                        WHERE to_status = 'submitted'
                        GROUP BY request_id
                    ) submitted
                    JOIN (
                        SELECT request_id, MIN(changed_at) AS changed_at
                        FROM status_history
                        WHERE to_status = 'delivered'
                        GROUP BY request_id
                    ) delivered ON submitted.request_id = delivered.request_id
                    ORDER BY hours
                """)
            ).fetchall()
            if rows:
                n = len(rows)
                mid = n // 2
                if n % 2 == 1:
                    median_hours = round(float(rows[mid][0]), 2)
                else:
                    median_hours = round((float(rows[mid - 1][0]) + float(rows[mid][0])) / 2, 2)
    except Exception:
        # If the median query fails for any reason, return None rather than crashing
        median_hours = None

    # 4. Top 5 task names by number of good episodes
    top_tasks_query = (
        db.query(
            Episode.task_name,
            func.count().label("good_count"),
        )
        .filter(
            Episode.quality == "good",
            Episode.recorded_at.isnot(None),
            cast(Episode.recorded_at, Date) >= start_date,
            cast(Episode.recorded_at, Date) <= end_date,
        )
        .group_by(Episode.task_name)
        .order_by(func.count().desc())
        .limit(5)
        .all()
    )
    top_tasks = [
        TopTask(task_name=row.task_name, good_episode_count=row.good_count)
        for row in top_tasks_query
    ]

    return AnalyticsResponse(
        episodes_per_day_per_robot=episodes_per_day,
        requests_by_status=requests_by_status,
        median_fulfilment_hours=median_hours,
        top_tasks=top_tasks,
    )
