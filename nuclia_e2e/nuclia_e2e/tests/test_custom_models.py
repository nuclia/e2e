from nuclia import get_regional_url
from nuclia import sdk
from nuclia.data import get_async_auth
from nuclia.sdk.auth import AsyncNucliaAuth
from nuclia_e2e.tests.conftest import ZoneConfig

import os
import pytest

TEST_ENV = os.environ.get("TEST_ENV")


@pytest.mark.asyncio_cooperative
@pytest.mark.skipif(TEST_ENV != "stage", reason="This test is only for stage environment")
async def test_generative(request: pytest.FixtureRequest, regional_api_config: ZoneConfig):
    kb_id = regional_api_config.permanent_kb_id
    zone = regional_api_config.zone_slug
    assert regional_api_config.global_config is not None
    account_slug = regional_api_config.global_config.permanent_account_slug

    sdk.NucliaAccounts().default(account_slug)

    auth = get_async_auth()
    account_id = auth.get_account_id(account_slug)

    # This model has been added to the vLLM server of the gke-stage-1 cluster for testing purposes
    qwen3_8b = "openai_compat:qwen3-8b"

    # Make sure there are no custom models configured
    await remove_all_models(auth, zone, account_id)
    assert len(await list_models(auth, zone, account_id)) == 0

    # Configure a new custom generative model
    await add_model(
        auth,
        zone,
        account_id,
        model_data={
            "name": "test_model",
            "id": qwen3_8b,
            "type": "GENERATIVE",
        },
        kbs=[kb_id],
    )

    # Ask a question using the new model
    answer = await sdk.AsyncNucliaSearch().ask(
        query="how to cook an omelette?",
        generative_model=qwen3_8b,
    )
    assert answer.answer is not None
    print(f"Answer: {answer.answer}")

    # Remove the custom model
    await remove_all_models(auth, zone, account_id)
    assert len(await list_models(auth, zone, account_id)) == 0


async def add_model(
    auth: AsyncNucliaAuth,
    zone: str,
    account_id: str,
    model_data: dict,
    kbs: list[str],
):
    # Add model to the account
    path = get_regional_url(zone, f"/api/v1/account/{account_id}/models")
    response = await auth._request("POST", path, data=model_data)
    model_id = response["id"]

    # Add model to the kbs
    for kb in kbs:
        path = get_regional_url(zone, f"/api/v1/account/{account_id}/models/{kb}")
        await auth._request("POST", path, data={"id": model_id})


async def list_models(auth: AsyncNucliaAuth, zone: str, account_id: str) -> list:
    path = get_regional_url(zone, f"/api/v1/account/{account_id}/models")
    models = await auth._request("GET", path)

    return models


async def delete_model(auth: AsyncNucliaAuth, zone: str, account_id: str, model_id: str):
    path = get_regional_url(zone, f"/api/v1/account/{account_id}/model/{model_id}")
    await auth._request("DELETE", path)


async def remove_all_models(auth: AsyncNucliaAuth, zone: str, account_id: str):
    models = await list_models(auth, zone, account_id)
    for model in models:
        await delete_model(auth, zone, account_id, model["id"])
