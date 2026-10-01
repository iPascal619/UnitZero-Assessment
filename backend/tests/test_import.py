"""Tests for CSV episode import.

Covers:
- Successful import of valid rows
- Idempotency: re-importing same file doesn't create duplicates
- Handling of duplicates within a single file
- Missing required fields are skipped with error reporting
- Invalid quality values are skipped
- Inconsistent formatting is normalized
"""

import pytest

VALID_CSV = """episode_id,robot_id,task_name,recorded_at,duration_seconds,operator_name,quality
EP-001,robot_arm_1,picking_cups,2024-01-15 09:30:00,45.2,Alice Johnson,good
EP-002,robot_arm_2,stacking_blocks,2024-01-15 10:00:00,38.7,Bob Smith,usable
EP-003,robot_arm_3,sorting_objects,2024-01-15 11:00:00,52.1,Charlie Davis,bad
"""

MESSY_CSV = """episode_id,robot_id,task_name,recorded_at,duration_seconds,operator_name,quality
EP-010,Robot_Arm_1,Picking_Cups,2024-01-15 09:30:00,45.2,alice johnson,Good
EP-011,robot_arm_2,STACKING_BLOCKS,2024-01-15 10:00:00,38.7,Bob Smith,USABLE
EP-010,Robot_Arm_1,Picking_Cups,2024-01-15 09:30:00,45.2,alice johnson,Good
EP-012,,picking_cups,2024-01-15 11:00:00,52.1,Charlie,good
EP-013,robot_arm_3,sorting_objects,2024-01-15 12:00:00,,Charlie Davis,good
EP-014,robot_arm_1,picking_cups,2024-01-15 13:00:00,40.0,Alice,
EP-015,robot_arm_2,picking_cups,2024-01-15 14:00:00,35.0,Bob,invalid_quality
"""


class TestImportBasic:
    def test_import_valid_csv(self, client, operator_headers):
        resp = client.post(
            "/api/episodes/import",
            headers=operator_headers,
            files={"file": ("episodes.csv", VALID_CSV.encode(), "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 3
        assert data["skipped"] == 0
        assert len(data["errors"]) == 0

    def test_import_creates_episodes_in_db(self, client, operator_headers):
        client.post(
            "/api/episodes/import",
            headers=operator_headers,
            files={"file": ("episodes.csv", VALID_CSV.encode(), "text/csv")},
        )
        # List episodes
        resp = client.get("/api/episodes", headers=operator_headers)
        assert resp.status_code == 200
        episodes = resp.json()
        assert len(episodes) == 3
        # Check they are there
        ids = {ep["episode_id"] for ep in episodes}
        assert ids == {"EP-001", "EP-002", "EP-003"}


class TestImportIdempotency:
    def test_reimport_same_file_no_duplicates(self, client, operator_headers):
        # First import
        resp1 = client.post(
            "/api/episodes/import",
            headers=operator_headers,
            files={"file": ("episodes.csv", VALID_CSV.encode(), "text/csv")},
        )
        assert resp1.json()["imported"] == 3

        # Second import of the same file
        resp2 = client.post(
            "/api/episodes/import",
            headers=operator_headers,
            files={"file": ("episodes.csv", VALID_CSV.encode(), "text/csv")},
        )
        data2 = resp2.json()
        assert data2["imported"] == 0
        assert data2["skipped"] == 3  # All skipped as already imported

        # Verify total count hasn't changed
        resp = client.get("/api/episodes", headers=operator_headers)
        assert len(resp.json()) == 3


class TestImportMessyData:
    def test_handles_duplicates_within_file(self, client, operator_headers):
        resp = client.post(
            "/api/episodes/import",
            headers=operator_headers,
            files={"file": ("messy.csv", MESSY_CSV.encode(), "text/csv")},
        )
        data = resp.json()
        # EP-010 appears twice, second should be skipped
        # EP-012 missing robot_id - skipped
        # EP-013 missing duration is OK (nullable)
        # EP-014 missing quality - skipped
        # EP-015 invalid quality - skipped
        assert data["imported"] == 3  # EP-010, EP-011, EP-013
        assert data["skipped"] == 4  # duplicate EP-010, missing robot_id, empty quality, invalid quality

    def test_normalizes_formatting(self, client, operator_headers):
        resp = client.post(
            "/api/episodes/import",
            headers=operator_headers,
            files={"file": ("messy.csv", MESSY_CSV.encode(), "text/csv")},
        )
        # Check normalized values
        eps_resp = client.get("/api/episodes", headers=operator_headers)
        episodes = {ep["episode_id"]: ep for ep in eps_resp.json()}

        # robot_id should be lowercased
        assert episodes["EP-010"]["robot_id"] == "robot_arm_1"
        # task_name should be lowercased
        assert episodes["EP-011"]["task_name"] == "stacking_blocks"
        # quality should be lowercased
        assert episodes["EP-010"]["quality"] == "good"
        assert episodes["EP-011"]["quality"] == "usable"

    def test_missing_required_fields_reported(self, client, operator_headers):
        resp = client.post(
            "/api/episodes/import",
            headers=operator_headers,
            files={"file": ("messy.csv", MESSY_CSV.encode(), "text/csv")},
        )
        data = resp.json()
        # Check that errors contain info about missing robot_id
        error_reasons = [e["reason"] for e in data["errors"]]
        assert any("robot_id" in r.lower() for r in error_reasons)

    def test_nullable_fields_accepted(self, client, operator_headers):
        """Episodes with missing optional fields (duration, operator_name, recorded_at) should import."""
        csv = """episode_id,robot_id,task_name,recorded_at,duration_seconds,operator_name,quality
EP-100,robot_1,task_a,,,,good
"""
        resp = client.post(
            "/api/episodes/import",
            headers=operator_headers,
            files={"file": ("test.csv", csv.encode(), "text/csv")},
        )
        data = resp.json()
        assert data["imported"] == 1
        assert data["skipped"] == 0
