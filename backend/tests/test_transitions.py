"""Tests for request status transitions.

Covers:
- Valid transitions with correct roles
- Invalid transitions rejected
- Wrong role for a transition
- Client can only accept/reject their own requests
- Cannot deliver without enough episodes assigned
- Every transition is recorded in status history
"""

import pytest
from app.models import Episode, Assignment


def _create_request(client, client_headers):
    """Helper to create a request and return its data."""
    resp = client.post(
        "/api/requests",
        headers=client_headers,
        json={
            "task_name": "picking_cups",
            "episodes_requested": 2,
            "deadline": "2025-12-31",
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _add_episodes_and_assign(db, client_http, operator_headers, request_id, count=2):
    """Helper: create episodes and assign them to a request."""
    episode_ids = []
    for i in range(count):
        ep = Episode(
            episode_id=f"TEST-EP-{request_id}-{i}",
            robot_id="robot_1",
            task_name="picking_cups",
            quality="good",
        )
        db.add(ep)
        db.flush()
        episode_ids.append(ep.id)
    db.commit()

    resp = client_http.post(
        f"/api/requests/{request_id}/assignments",
        headers=operator_headers,
        json={"episode_ids": episode_ids},
    )
    assert resp.status_code == 201
    return episode_ids


class TestValidTransitions:
    def test_submitted_to_in_progress(self, client, client_headers, operator_headers):
        req = _create_request(client, client_headers)
        resp = client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "in_progress"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

    def test_in_progress_to_delivered(
        self, client, db, client_headers, operator_headers
    ):
        req = _create_request(client, client_headers)
        # Move to in_progress
        client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "in_progress"},
        )
        # Assign enough episodes
        _add_episodes_and_assign(db, client, operator_headers, req["id"], 2)
        # Deliver
        resp = client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "delivered"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "delivered"

    def test_delivered_to_accepted(
        self, client, db, client_headers, operator_headers
    ):
        req = _create_request(client, client_headers)
        client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "in_progress"},
        )
        _add_episodes_and_assign(db, client, operator_headers, req["id"], 2)
        client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "delivered"},
        )
        resp = client.patch(
            f"/api/requests/{req['id']}/status",
            headers=client_headers,
            json={"status": "accepted"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    def test_delivered_to_rejected(
        self, client, db, client_headers, operator_headers
    ):
        req = _create_request(client, client_headers)
        client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "in_progress"},
        )
        _add_episodes_and_assign(db, client, operator_headers, req["id"], 2)
        client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "delivered"},
        )
        resp = client.patch(
            f"/api/requests/{req['id']}/status",
            headers=client_headers,
            json={"status": "rejected", "notes": "Quality not good enough"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_rejected_to_in_progress_rework(
        self, client, db, client_headers, operator_headers
    ):
        req = _create_request(client, client_headers)
        client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "in_progress"},
        )
        _add_episodes_and_assign(db, client, operator_headers, req["id"], 2)
        client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "delivered"},
        )
        client.patch(
            f"/api/requests/{req['id']}/status",
            headers=client_headers,
            json={"status": "rejected"},
        )
        # Operator reworks
        resp = client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "in_progress"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"


class TestInvalidTransitions:
    def test_submitted_to_delivered_invalid(self, client, client_headers, operator_headers):
        req = _create_request(client, client_headers)
        resp = client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "delivered"},
        )
        assert resp.status_code == 400
        assert "Invalid transition" in resp.json()["detail"]

    def test_submitted_to_accepted_invalid(self, client, client_headers):
        req = _create_request(client, client_headers)
        resp = client.patch(
            f"/api/requests/{req['id']}/status",
            headers=client_headers,
            json={"status": "accepted"},
        )
        assert resp.status_code == 400

    def test_in_progress_to_accepted_invalid(
        self, client, client_headers, operator_headers
    ):
        req = _create_request(client, client_headers)
        client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "in_progress"},
        )
        resp = client.patch(
            f"/api/requests/{req['id']}/status",
            headers=client_headers,
            json={"status": "accepted"},
        )
        assert resp.status_code == 400


class TestTransitionRoleEnforcement:
    def test_client_cannot_move_to_in_progress(self, client, client_headers):
        req = _create_request(client, client_headers)
        resp = client.patch(
            f"/api/requests/{req['id']}/status",
            headers=client_headers,
            json={"status": "in_progress"},
        )
        assert resp.status_code == 403

    def test_operator_cannot_accept(
        self, client, db, client_headers, operator_headers
    ):
        req = _create_request(client, client_headers)
        client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "in_progress"},
        )
        _add_episodes_and_assign(db, client, operator_headers, req["id"], 2)
        client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "delivered"},
        )
        resp = client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "accepted"},
        )
        assert resp.status_code == 403


class TestDeliveryPrerequisite:
    def test_cannot_deliver_without_enough_episodes(
        self, client, client_headers, operator_headers
    ):
        req = _create_request(client, client_headers)
        client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "in_progress"},
        )
        # Try to deliver with 0 episodes assigned (need 2)
        resp = client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "delivered"},
        )
        assert resp.status_code == 400
        assert "0/2" in resp.json()["detail"]

    def test_cannot_deliver_with_partial_episodes(
        self, client, db, client_headers, operator_headers
    ):
        req = _create_request(client, client_headers)
        client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "in_progress"},
        )
        # Assign only 1 of 2 required
        _add_episodes_and_assign(db, client, operator_headers, req["id"], 1)
        resp = client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "delivered"},
        )
        assert resp.status_code == 400
        assert "1/2" in resp.json()["detail"]


class TestStatusHistory:
    def test_transitions_are_recorded(
        self, client, db, client_headers, operator_headers
    ):
        req = _create_request(client, client_headers)
        client.patch(
            f"/api/requests/{req['id']}/status",
            headers=operator_headers,
            json={"status": "in_progress"},
        )

        resp = client.get(
            f"/api/requests/{req['id']}/history", headers=client_headers
        )
        assert resp.status_code == 200
        history = resp.json()
        # Initial "submitted" + transition to "in_progress"
        assert len(history) == 2
        assert history[0]["to_status"] == "submitted"
        assert history[1]["from_status"] == "submitted"
        assert history[1]["to_status"] == "in_progress"
