"""
Google Gmail List Emails – Comprehensive Integration Tests

Covers List Emails operation with:
- BEST cases: happy path listing inbox emails and basic successful response checks
- GOOD cases: search/filter variations
- WORSE cases: invalid inputs that should fail validation

Run with real Google Gmail credentials:
pytest .\test\google\gmail\test_list_gmail.py -v
pytest .\test\google\gmail\test_list_gmail.py -v -k "best"
pytest .\test\google\gmail\test_list_gmail.py -v -k "good"
pytest .\test\google\gmail\test_list_gmail.py -v -k "worse"
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


def make_list_gmail_payload(
    label_ids=None,
    query=None,
    max_results=10,
    include_spam_trash=False,
    order_by="descending",
):
    """Build a Gmail list_emails request payload."""
    inputs = {}

    if label_ids is not None:
        inputs["label_ids"] = label_ids
    if query is not None:
        inputs["query"] = query
    if max_results is not None:
        inputs["max_results"] = max_results
    if include_spam_trash is not None:
        inputs["include_spam_trash"] = include_spam_trash
    if order_by is not None:
        inputs["order_by"] = order_by

    return {
        "service": "gmail",
        "action": "list_emails",
        "inputs": inputs,
    }


class TestGmailListBestCases:
    """Happy path tests for Gmail list_emails."""

    async def test_list_emails_default_inbox(self):
        # Verifies list_emails works with default valid inputs.
        payload = make_list_gmail_payload()
        r = await execute(payload)

        assert r.status_code == 200
        body = r.json()
        result = body.get("result", {})

        assert body.get("service") == "gmail"
        assert body.get("action") == "list_emails"
        assert isinstance(result.get("messages"), list)
        assert isinstance(result.get("total_count"), int)

    async def test_list_emails_response_with_pagination_fields(self):
        # Verifies successful response includes standard list metadata fields.
        payload = make_list_gmail_payload(max_results=5)
        r = await execute(payload)

        assert r.status_code == 200
        result = r.json().get("result", {})

        assert "messages" in result
        assert "total_count" in result
        assert "next_page_token" in result
        assert "query_used" in result

    async def test_list_emails_respects_max_results(self):
        # Verifies returned messages do not exceed requested max_results.
        payload = make_list_gmail_payload(max_results=5)
        r = await execute(payload)

        assert r.status_code == 200
        result = r.json().get("result", {})
        messages = result.get("messages", [])

        assert isinstance(messages, list)
        assert len(messages) <= 5

    async def test_list_emails_returns_message_objects(self):
        # Verifies returned list items are message objects.
        payload = make_list_gmail_payload(max_results=5)
        r = await execute(payload)

        assert r.status_code == 200
        result = r.json().get("result", {})
        messages = result.get("messages", [])

        assert isinstance(messages, list)
        if messages:
            assert isinstance(messages[0], dict)


class TestGmailListGoodCases:
    """Good variations for Gmail list_emails."""

    async def test_list_emails_with_query(self):
        # Verifies list_emails supports query filtering.
        query = "from:noreply@example.com"
        payload = make_list_gmail_payload(query=query, max_results=5)
        r = await execute(payload)

        assert r.status_code == 200
        result = r.json().get("result", {})

        assert isinstance(result.get("messages"), list)
        assert len(result.get("messages", [])) <= 5

    async def test_list_emails_with_label_filters(self):
        # Verifies list_emails supports Gmail label filters.
        payload = make_list_gmail_payload(
            label_ids=["INBOX"],
            max_results=5,
            order_by="ascending",
        )
        r = await execute(payload)

        assert r.status_code == 200
        result = r.json().get("result", {})

        assert isinstance(result.get("messages"), list)
        assert len(result.get("messages", [])) <= 5

    async def test_list_emails_with_query_and_spam_trash(self):
        # Verifies query and include_spam_trash can be used together.
        payload = make_list_gmail_payload(
            query="invoice",
            max_results=5,
            include_spam_trash=True,
        )
        r = await execute(payload)

        assert r.status_code == 200
        result = r.json().get("result", {})

        assert isinstance(result.get("messages"), list)

    async def test_list_emails_with_empty_query(self):
        # Verifies empty string query is handled cleanly.
        payload = make_list_gmail_payload(query="", max_results=5)
        r = await execute(payload)

        assert r.status_code == 200
        result = r.json().get("result", {})

        assert isinstance(result.get("messages"), list)


class TestGmailListWorseCases:
    """Worse cases for Gmail list_emails validation and error handling."""

    async def test_invalid_max_results_zero(self):
        # Verifies max_results below minimum is rejected.
        payload = make_list_gmail_payload(max_results=0)
        r = await execute(payload)

        assert r.status_code >= 400

    async def test_invalid_max_results_negative(self):
        # Verifies negative max_results is rejected.
        payload = make_list_gmail_payload(max_results=-1)
        r = await execute(payload)

        assert r.status_code >= 400

    async def test_invalid_label_ids_type(self):
        # Verifies label_ids must be a list, not a string.
        payload = make_list_gmail_payload(label_ids="INBOX")
        r = await execute(payload)

        assert r.status_code >= 400

    async def test_invalid_query_type(self):
        # Verifies query must be a string.
        payload = make_list_gmail_payload(query=12345)
        r = await execute(payload)

        assert r.status_code >= 400

    async def test_invalid_include_spam_trash_type(self):
        # Verifies include_spam_trash must be a boolean.
        payload = make_list_gmail_payload(include_spam_trash="yes")
        r = await execute(payload)

        assert r.status_code >= 400

    async def test_invalid_order_by_value(self):
        # Verifies unsupported order_by values are rejected or safely handled.
        payload = make_list_gmail_payload(order_by="sideways")
        r = await execute(payload)

        assert r.status_code >= 400