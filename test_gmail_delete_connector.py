"""
Google Gmail Delete Email - Comprehensive Integration Tests

Covers delete_email operation with:
- BEST cases: soft delete (move to Trash)
- WORSE cases: invalid message_id

Run with real Google Gmail credentials:
pytest .\\tests\\test_gmail_delete_connector.py -v
pytest .\\tests\\test_gmail_delete_connector.py -v -k \"best\"
pytest .\\tests\\test_gmail_delete_connector.py -v -k \"worse\"
"""

import os

import httpx
import pytest

BASE_URL = os.getenv("TEST_API_BASE_URL")
WORKSPACE_ID = os.getenv("TEST_WORKSPACE_ID")
USER_ID = os.getenv("TEST_USER_ID", "user123")

if not all([BASE_URL, WORKSPACE_ID]):
    pytest.skip(
        "Missing TEST_API_BASE_URL or TEST_WORKSPACE_ID",
        allow_module_level=True,
    )

EXECUTE_URL = f"{BASE_URL}/api/v1/workspaces/{WORKSPACE_ID}/execute"

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def execute(payload: dict) -> httpx.Response:
    """Execute action payload against the workspace execute endpoint."""
    async with httpx.AsyncClient(timeout=60) as client:
        return await client.post(
            f"{EXECUTE_URL}?user_id={USER_ID}",
            json=payload,
        )


def make_delete_email_payload(message_id: str, permanent: bool = False):
    """Build a Gmail delete_email request payload."""
    return {
        "service": "gmail",
        "action": "delete_email",
        "inputs": {
            "message_id": message_id,
            "permanent": permanent,
        },
    }


class TestGmailDeleteBestCases:
    """Happy path tests for Gmail delete_email."""

    async def test_soft_delete_moves_to_trash(self):
        # Verifies delete_email soft-deletes (moves to Trash) when permanent=False.
        msg_id = os.getenv("TEST_GMAIL_DELETE_MESSAGE_ID") or os.getenv("TEST_GMAIL_MESSAGE_ID")
        if not msg_id:
            pytest.skip("TEST_GMAIL_DELETE_MESSAGE_ID or TEST_GMAIL_MESSAGE_ID not set")

        payload = make_delete_email_payload(message_id=msg_id, permanent=False)
        r = await execute(payload)

        assert r.status_code == 200
        result = r.json().get("result", {})

        assert result.get("message_id") == msg_id
        assert result.get("deleted") is True
        assert result.get("permanent") is False

    async def test_soft_delete_already_trashed(self):
        # Verifies soft delete behaves when the message is already in Trash.
        msg_id = os.getenv("TEST_GMAIL_TRASH_MESSAGE_ID") or os.getenv("TEST_GMAIL_MESSAGE_ID")
        if not msg_id:
            pytest.skip("TEST_GMAIL_TRASH_MESSAGE_ID or TEST_GMAIL_MESSAGE_ID not set")

        payload = make_delete_email_payload(message_id=msg_id, permanent=False)
        r = await execute(payload)

        assert r.status_code in (200, 204)
        result = r.json().get("result", {}) if r.content else {}

        # When 204 No Content, result may be empty; ensure no failure occurs.
        if result:
            assert result.get("message_id") == msg_id
            assert result.get("deleted") is True

class TestGmailDeleteGoodCases:
    """Good variations for Gmail delete_email."""

    async def test_permanent_delete(self):
        # Verifies permanent delete succeeds when requested.
        msg_id = os.getenv("TEST_GMAIL_DELETE_MESSAGE_ID") or os.getenv("TEST_GMAIL_MESSAGE_ID")
        if not msg_id:
            pytest.skip("TEST_GMAIL_DELETE_MESSAGE_ID or TEST_GMAIL_MESSAGE_ID not set")

        payload = make_delete_email_payload(message_id=msg_id, permanent=True)
        r = await execute(payload)

        assert r.status_code == 200
        result = r.json().get("result", {})

        assert result.get("message_id") == msg_id
        assert result.get("deleted") is True
        assert result.get("permanent") is True

    async def test_delete_then_idempotent_repeat(self):
        # Verifies a second delete call is tolerated (idempotency-ish).
        msg_id = os.getenv("TEST_GMAIL_DELETE_MESSAGE_ID") or os.getenv("TEST_GMAIL_MESSAGE_ID")
        if not msg_id:
            pytest.skip("TEST_GMAIL_DELETE_MESSAGE_ID or TEST_GMAIL_MESSAGE_ID not set")

        payload = make_delete_email_payload(message_id=msg_id, permanent=False)

        first = await execute(payload)
        assert first.status_code in (200, 204)

        second = await execute(payload)
        assert second.status_code in (200, 204, 404, 410)

        # If a body exists, basic shape check
        if second.content:
            result = second.json().get("result", {})
            if result:
                assert result.get("message_id") == msg_id

class TestGmailDeleteWorseCases:
    """Validation and error handling for Gmail delete_email."""

    async def test_delete_invalid_message_id(self):
        # Verifies invalid message_id results in error response.
        payload = make_delete_email_payload(message_id="bad-id")
        r = await execute(payload)

        assert r.status_code >= 400

    async def test_delete_missing_message_id(self):
        # Verifies missing message_id is rejected.
        payload = {
            "service": "gmail",
            "action": "delete_email",
            "inputs": {"permanent": False},
        }
        r = await execute(payload)

        assert r.status_code in (400, 422)
