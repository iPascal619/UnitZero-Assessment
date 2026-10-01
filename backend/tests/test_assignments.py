"""Tests for episode assignment rules.

Covers:
- Only good/usable episodes can be assigned
- An episode can be assigned to at most one request
- Cannot assign to delivered/accepted requests
- Successful assignment
- Assignment removal
"""

import pytest
from app.models import Episode


def _seed_episodes(db, count=5, quality="good"):
    """Helper to create test episodes."""
    episodes = []
    for i in range(count):
        ep = Episode(
            episode_id=f"ASSIGN-EP-{quality}-{i}",
            robot_id="robot_1",
            task_name="picking_cups",
            quality=quality,
        )
        db.add(ep)
        episodes.append(ep)
    db.commit()
    for ep in episodes:
        db.refresh(ep)
    return episodes


def _create_request(client, client_headers, episodes_requested=2):
    resp = client.post(
        "/api/requests",
        headers=client_headers,
        json={
            "task_name": "picking_cups",
            "episodes_requested": episodes_requested,
            "deadline": "2025-12-31",
        },
    )
    assert resp.status_code == 201
    return resp.json()


class TestAssignmentQuality:
    def test_assign_good_episodes(
        self, client, db, client_headers, operator_headers
    ):
        req = _create_request(client, client_headers)
        episodes = _seed_episodes(db, 2, "good")
        resp = client.post(
            f"/api/requests/{req['id']}/assignments",
            headers=operator_headers,
            json={"episode_ids": [ep.id for ep in episodes]},
        )
        assert resp.status_code == 201
        assert len(resp.json()) == 2

    def test_assign_usable_episodes(
        self, client, db, client_headers, operator_headers
    ):
        req = _create_request(client, client_headers)
        episodes = _seed_episodes(db, 2, "usable")
        resp = client.post(
            f"/api/requests/{req['id']}/assignments",
            headers=operator_headers,
            json={"episode_ids": [ep.id for ep in episodes]},
        )
        assert resp.status_code == 201

    def test_cannot_assign_bad_episodes(
        self, client, db, client_headers, operator_headers
    ):
        req = _create_request(client, client_headers)
        episodes = _seed_episodes(db, 2, "bad")
        resp = client.post(
            f"/api/requests/{req['id']}/assignments",
            headers=operator_headers,
            json={"episode_ids": [ep.id for ep in episodes]},
        )
        assert resp.status_code == 400
        assert "quality" in resp.json()["detail"].lower()


class TestAssignmentUniqueness:
    def test_episode_cannot_be_assigned_twice(
        self, client, db, client_headers, operator_headers
    ):
        req1 = _create_request(client, client_headers)
        req2 = _create_request(client, client_headers)
        episodes = _seed_episodes(db, 2, "good")

        # Assign to first request
        resp1 = client.post(
            f"/api/requests/{req1['id']}/assignments",
            headers=operator_headers,
            json={"episode_ids": [episodes[0].id]},
        )
        assert resp1.status_code == 201

        # Try to assign same episode to second request
        resp2 = client.post(
            f"/api/requests/{req2['id']}/assignments",
            headers=operator_headers,
            json={"episode_ids": [episodes[0].id]},
        )
        assert resp2.status_code == 400
        assert "already assigned" in resp2.json()["detail"].lower()


class TestAssignmentStatusRestriction:
    def test_cannot_assign_to_delivered_request(
        self, client, db, client_headers, operator_headers
    ):
        req = _create_request(client, client_headers)
        episodes = _seed_episodes(db, 4, "good")

        # Move through workflow to delivered
        client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "in_progress"},
        )
        client.post(
            f"/api/requests/{req['id']}/assignments",
            headers=operator_headers,
            json={"episode_ids": [episodes[0].id, episodes[1].id]},
        )
        client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "delivered"},
        )

        # Try to assign more episodes
        resp = client.post(
            f"/api/requests/{req['id']}/assignments",
            headers=operator_headers,
            json={"episode_ids": [episodes[2].id]},
        )
        assert resp.status_code == 400

    def test_cannot_assign_to_accepted_request(
        self, client, db, client_headers, operator_headers
    ):
        req = _create_request(client, client_headers)
        episodes = _seed_episodes(db, 4, "good")

        # Move through full workflow to accepted
        client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "in_progress"},
        )
        client.post(
            f"/api/requests/{req['id']}/assignments",
            headers=operator_headers,
            json={"episode_ids": [episodes[0].id, episodes[1].id]},
        )
        client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "delivered"},
        )
        client.patch(
            f"/api/requests/{req['id']}/status",
            headers=client_headers,
            json={"status": "accepted"},
        )

        resp = client.post(
            f"/api/requests/{req['id']}/assignments",
            headers=operator_headers,
            json={"episode_ids": [episodes[2].id]},
        )
        assert resp.status_code == 400


class TestAssignmentRemoval:
    def test_remove_assignment(
        self, client, db, client_headers, operator_headers
    ):
        req = _create_request(client, client_headers)
        episodes = _seed_episodes(db, 2, "good")

        resp = client.post(
            f"/api/requests/{req['id']}/assignments",
            headers=operator_headers,
            json={"episode_ids": [episodes[0].id]},
        )
        assignment_id = resp.json()[0]["id"]

        resp = client.delete(
            f"/api/requests/{req['id']}/assignments/{assignment_id}",
            headers=operator_headers,
        )
        assert resp.status_code == 204

        # Verify episode is free to assign again
        resp = client.post(
            f"/api/requests/{req['id']}/assignments",
            headers=operator_headers,
            json={"episode_ids": [episodes[0].id]},
        )
        assert resp.status_code == 201


class TestClientCannotAssign:
    def test_client_cannot_assign_episodes(
        self, client, db, client_headers
    ):
        req = _create_request(client, client_headers)
        episodes = _seed_episodes(db, 2, "good")
        resp = client.post(
            f"/api/requests/{req['id']}/assignments",
            headers=client_headers,
            json={"episode_ids": [ep.id for ep in episodes]},
        )
        assert resp.status_code == 403
