"""CSV import service for episodes.

Handles messy data: duplicates, missing values, inconsistent formatting.
Designed to be idempotent — safe to run multiple times on the same file.
"""

import csv
import io
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Episode


# Allowed quality values after normalization
VALID_QUALITIES = {"good", "usable", "bad"}


def _normalize(value: str | None) -> str | None:
    """Strip whitespace and lowercase."""
    if value is None:
        return None
    v = value.strip()
    return v if v else None


def _normalize_quality(raw: str | None) -> str | None:
    """Normalize quality to lowercase; return None if invalid."""
    v = _normalize(raw)
    if v is None:
        return None
    v = v.lower()
    return v if v in VALID_QUALITIES else None


def _parse_datetime(raw: str | None) -> datetime | None:
    """Parse datetime from various formats found in messy CSV exports."""
    v = _normalize(raw)
    if v is None:
        return None

    # Strip trailing timezone indicator (we store as naive UTC)
    v = v.rstrip("Z").rstrip("+00:00")

    # Try common formats in order of likelihood
    formats = [
        "%Y-%m-%dT%H:%M:%S",    # ISO 8601 with T separator
        "%Y-%m-%d %H:%M:%S",    # Space-separated
        "%Y-%m-%dT%H:%M",       # ISO 8601 without seconds
        "%Y-%m-%d %H:%M",       # Space-separated without seconds
        "%d/%m/%Y %H:%M",       # European format
        "%m/%d/%Y %H:%M:%S",    # US format
        "%Y-%m-%d",             # Date only
    ]
    for fmt in formats:
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    return None


def _parse_float(raw: str | None) -> float | None:
    v = _normalize(raw)
    if v is None:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def import_episodes_from_csv(db: Session, file_content: str) -> dict:
    """Import episodes from CSV content.

    Returns a summary dict with imported, skipped, errors, and details.
    """
    reader = csv.DictReader(io.StringIO(file_content))

    imported = 0
    skipped = 0
    errors = []
    details = []

    # Pre-load existing episode_ids to avoid N+1 queries
    existing_ids = set(
        row[0] for row in db.query(Episode.episode_id).all()
    )

    seen_in_file: set[str] = set()  # Track IDs within this import batch

    for row_num, row in enumerate(reader, start=2):  # Row 1 is header
        episode_id = _normalize(row.get("episode_id"))

        # ── Validation ────────────────────────────────────────────────────
        if not episode_id:
            errors.append({"row": row_num, "reason": "Missing episode_id"})
            skipped += 1
            continue

        # Duplicate within file
        if episode_id in seen_in_file:
            details.append(f"Row {row_num}: Skipped duplicate in file: {episode_id}")
            skipped += 1
            continue

        seen_in_file.add(episode_id)

        # Already in database (idempotency)
        if episode_id in existing_ids:
            details.append(
                f"Row {row_num}: Skipped already-imported: {episode_id}"
            )
            skipped += 1
            continue

        robot_id = _normalize(row.get("robot_id"))
        if not robot_id:
            errors.append(
                {"row": row_num, "episode_id": episode_id, "reason": "Missing robot_id"}
            )
            skipped += 1
            continue

        task_name = _normalize(row.get("task_name"))
        if not task_name:
            errors.append(
                {"row": row_num, "episode_id": episode_id, "reason": "Missing task_name"}
            )
            skipped += 1
            continue

        quality = _normalize_quality(row.get("quality"))
        if quality is None:
            errors.append(
                {
                    "row": row_num,
                    "episode_id": episode_id,
                    "reason": f"Missing or invalid quality: '{row.get('quality', '')}'",
                }
            )
            skipped += 1
            continue

        # ── Normalize & create ────────────────────────────────────────────
        episode = Episode(
            episode_id=episode_id,
            robot_id=robot_id.lower(),
            task_name=task_name.lower().replace(" ", "_"),
            recorded_at=_parse_datetime(row.get("recorded_at")),
            duration_seconds=_parse_float(row.get("duration_seconds")),
            operator_name=_normalize(row.get("operator_name")),
            quality=quality,
        )
        db.add(episode)
        existing_ids.add(episode_id)
        imported += 1
        details.append(f"Row {row_num}: Imported {episode_id}")

    db.commit()

    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "details": details,
    }
