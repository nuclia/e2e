from nuclia_e2e.tests.conftest import RegionalAPI
from uuid import uuid4

import pytest


async def _delete_if_present(regional_api: RegionalAPI, path: str) -> None:
    async with regional_api.session.delete(
        f"{regional_api.base_url}{path}",
        headers=regional_api.auth_headers,
    ) as response:
        assert response.status in (204, 404), await response.text()


@pytest.mark.asyncio_cooperative
async def test_agentic_source_and_config_lifecycle(regional_api: RegionalAPI, kb_id: str):
    suffix = uuid4().hex
    source_id = f"e2e-source-{suffix}"
    config_id = f"e2e-config-{suffix}"
    source_path = f"/api/v1/kb/{kb_id}/sources/{source_id}"
    config_path = f"/api/v1/kb/{kb_id}/agentic_configs/{config_id}"
    source_payload = {
        "type": "nucliadb",
        "description": "NucliaDB E2E source",
    }
    config_payload = {
        "title": "NucliaDB E2E agent",
        "smart_agent": {"mode": "reactive", "sources": [source_id]},
        "summarize": {},
    }

    try:
        async with regional_api.session.post(
            f"{regional_api.base_url}{source_path}",
            headers=regional_api.auth_headers,
            json=source_payload,
        ) as response:
            assert response.status == 201, await response.text()

        async with regional_api.session.post(
            f"{regional_api.base_url}{config_path}",
            headers=regional_api.auth_headers,
            json=config_payload,
        ) as response:
            assert response.status == 201, await response.text()

        async with regional_api.session.get(
            f"{regional_api.base_url}{config_path}",
            headers=regional_api.auth_headers,
        ) as response:
            assert response.status == 200, await response.text()
            config = await response.json()
            assert config["title"] == config_payload["title"]
            assert config["smart_agent"]["sources"] == [source_id]

        async with regional_api.session.get(
            f"{regional_api.base_url}/api/v1/kb/{kb_id}/agentic_configs",
            headers=regional_api.auth_headers,
        ) as response:
            assert response.status == 200, await response.text()
            assert config_id in await response.json()

        async with regional_api.session.delete(
            f"{regional_api.base_url}{source_path}",
            headers=regional_api.auth_headers,
        ) as response:
            assert response.status == 409, await response.text()

        updated_payload = {"title": "Updated NucliaDB E2E agent"}
        async with regional_api.session.patch(
            f"{regional_api.base_url}{config_path}",
            headers=regional_api.auth_headers,
            json=updated_payload,
        ) as response:
            assert response.status == 204, await response.text()

        async with regional_api.session.get(
            f"{regional_api.base_url}{config_path}",
            headers=regional_api.auth_headers,
        ) as response:
            assert response.status == 200, await response.text()
            assert await response.json() == updated_payload
    finally:
        await _delete_if_present(regional_api, config_path)
        await _delete_if_present(regional_api, source_path)


@pytest.mark.asyncio_cooperative
async def test_agentic_ask_with_nucliadb_source(regional_api: RegionalAPI, kb_id: str):
    suffix = uuid4().hex
    source_id = f"e2e-ask-source-{suffix}"
    config_id = f"e2e-ask-config-{suffix}"
    source_path = f"/api/v1/kb/{kb_id}/sources/{source_id}"
    config_path = f"/api/v1/kb/{kb_id}/agentic_configs/{config_id}"

    try:
        async with regional_api.session.post(
            f"{regional_api.base_url}{source_path}",
            headers=regional_api.auth_headers,
            json={"type": "nucliadb", "description": "E2E recipe knowledge base"},
        ) as response:
            assert response.status == 201, await response.text()

        async with regional_api.session.post(
            f"{regional_api.base_url}{config_path}",
            headers=regional_api.auth_headers,
            json={
                "title": "NucliaDB recipe agent",
                "smart_agent": {"mode": "reactive", "sources": [source_id]},
                "summarize": {},
            },
        ) as response:
            assert response.status == 201, await response.text()

        headers = {**regional_api.auth_headers, "X-Synchronous": "true"}
        async with regional_api.session.post(
            f"{regional_api.base_url}/api/v1/kb/{kb_id}/ask",
            headers=headers,
            json={
                "query": "What is the main ingredient used to cook an omelette?",
                "agentic_config_id": config_id,
            },
        ) as response:
            assert response.status == 200, await response.text()
            result = await response.json()

        assert "egg" in result["answer"].lower()
        assert result["citations"]
    finally:
        await _delete_if_present(regional_api, config_path)
        await _delete_if_present(regional_api, source_path)
