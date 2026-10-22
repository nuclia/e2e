from nuclia_e2e.tests.conftest import RegionalAPI
from nuclia_e2e.tests.conftest import TEST_ENV
from nuclia_e2e.tests.conftest import ZoneConfig
from typing import Any
from uuid import uuid4

import aiohttp
import pytest

FLAGGED_CONTENT = "How should I grow tomatoes in a balcony garden?"
SAFE_CONTENT = "What is the capital of Portugal?"
POLICY_DESCRIPTION = "Temporary gardening policy for the NuaGuard E2E test."
POLICY_INSTRUCTION = (
    "Flag requests for practical advice about cultivating or caring for real plants. "
    "This includes growing vegetables, flowers, trees, houseplants, and indoor or "
    "outdoor herbs. Do not flag figurative uses of plant or garden words or requests "
    "unrelated to caring for real plants."
)
POLICY_QUERY = "Is the user asking for practical help growing or caring for a real plant?"


async def response_json(response: aiohttp.ClientResponse, expected_status: int) -> Any:
    body = await response.text()
    assert response.status == expected_status, body
    return await response.json()


def nua_headers(nua_key: str) -> dict[str, str]:
    authorization = nua_key if nua_key.lower().startswith("bearer ") else f"Bearer {nua_key}"
    return {"X-NUCLIA-NUAKEY": authorization}


def assert_decision(result: dict[str, Any], *, flagged: bool, policy_id: str | None) -> None:
    assert result["flagged"] is flagged
    assert result["policy_id"] == policy_id
    assert isinstance(result["score"], int | float)
    assert result["threshold"] == 0.5


def assert_blocked(body: dict[str, Any], *, openai_compatible: bool) -> None:
    envelope = "error" if openai_compatible else "detail"
    descriptions = "details" if openai_compatible else "descriptions"
    assert body[envelope]["code"] == "guardrail_blocked"
    assert POLICY_DESCRIPTION in body[envelope][descriptions]


@pytest.mark.skipif(TEST_ENV not in {"stage", "prod"}, reason="NuaGuard is not enabled in this environment")
@pytest.mark.asyncio_cooperative
async def test_nuaguard_policy_and_chat_enforcement(
    regional_api: RegionalAPI,
    regional_api_config: ZoneConfig,
    account_id: str,
):
    account_path = f"/api/v1/account/{account_id}/guardrail_policies"
    policy_id: str | None = None
    headers = nua_headers(regional_api_config.permanent_nua_key)

    try:
        async with regional_api.session.post(
            f"{regional_api.base_url}{account_path}",
            headers=regional_api.auth_headers,
            json={
                "name": f"NuaGuard E2E {uuid4().hex}",
                "description": POLICY_DESCRIPTION,
                "instruction": POLICY_INSTRUCTION,
                "query": POLICY_QUERY,
                "target": "QUERY",
                "enabled": False,
                "blocking": True,
            },
        ) as response:
            created = await response_json(response, 201)

        policy_id = created["id"]
        assert created["enabled"] is False
        assert created["blocking"] is True
        policy_path = f"{account_path}/{policy_id}"

        async with regional_api.session.get(
            f"{regional_api.base_url}{policy_path}",
            headers=regional_api.auth_headers,
        ) as response:
            fetched = await response_json(response, 200)
        assert fetched["id"] == policy_id

        async with regional_api.session.post(
            f"{regional_api.base_url}/api/v1/predict/guardrail",
            headers=headers,
            json={"content": FLAGGED_CONTENT, "policy_id": policy_id},
        ) as response:
            flagged = await response_json(response, 200)
        assert_decision(flagged, flagged=True, policy_id=policy_id)

        async with regional_api.session.post(
            f"{regional_api.base_url}/api/v1/predict/guardrail",
            headers=headers,
            json={"content": SAFE_CONTENT, "policy_id": policy_id},
        ) as response:
            allowed = await response_json(response, 200)
        assert_decision(allowed, flagged=False, policy_id=policy_id)

        async with regional_api.session.patch(
            f"{regional_api.base_url}{policy_path}",
            headers=regional_api.auth_headers,
            json={"enabled": True},
        ) as response:
            enabled = await response_json(response, 200)
        assert enabled["enabled"] is True

        async with regional_api.session.post(
            f"{regional_api.base_url}/api/v1/predict/chat",
            headers=headers,
            json={"question": FLAGGED_CONTENT},
        ) as response:
            standard_chat = await response_json(response, 400)
        assert_blocked(standard_chat, openai_compatible=False)

        async with regional_api.session.post(
            f"{regional_api.base_url}/api/v1/predict/compat/chat/completions",
            headers=headers,
            json={"messages": [{"role": "user", "content": FLAGGED_CONTENT}]},
        ) as response:
            openai_chat = await response_json(response, 400)
        assert_blocked(openai_chat, openai_compatible=True)
    finally:
        if policy_id is not None:
            async with regional_api.session.delete(
                f"{regional_api.base_url}{account_path}/{policy_id}",
                headers=regional_api.auth_headers,
            ) as response:
                assert response.status in (204, 404), await response.text()
