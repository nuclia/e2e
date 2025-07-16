from nuclia import get_regional_url
from nuclia import sdk
from nuclia.data import get_async_auth
from nuclia.sdk.auth import AsyncNucliaAuth
from nuclia_e2e.tests.conftest import ZoneConfig

import os
import pytest

TEST_ENV = os.environ.get("TEST_ENV")


@pytest.mark.asyncio_cooperative
@pytest.mark.skipif(TEST_ENV != "stage")
async def test_generative(request: pytest.FixtureRequest, regional_api_config: ZoneConfig):
    kb_id = regional_api_config.permanent_kb_id
    zone = regional_api_config.zone_slug
    assert regional_api_config.global_config is not None
    account_slug = regional_api_config.global_config.permanent_account_slug
    sdk.NucliaAccounts().default(account_slug)

    auth = get_async_auth()

    # This model has been added to the vLLM server of the gke-stage-1 cluster for testing purposes
    qwen3_8b = "openai_compat:qwen3-8b"

    # Make sure all the models
    await remove_all_models(auth, zone, account_slug)
    assert len(await list_models(auth, zone, account_slug)) == 0

    # Configure a new generative model
    await add_model(
        auth,
        zone,
        account_slug,
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

    # Remove the model
    await remove_all_models(auth, zone, account_slug)
    assert len(await list_models(auth, zone, account_slug)) == 0


async def add_model(
    auth: AsyncNucliaAuth,
    zone: str,
    account_slug: str,
    model_data: dict,
    kbs: list[str],
):
    account_id = auth.get_account_id(account_slug)

    # Add model to the account
    add_model_endpoint = f"/api/v1/account/{account_id}/model"
    path = get_regional_url(zone, add_model_endpoint)
    response = await auth._request("POST", path, data=model_data)
    model_id = response["id"]

    # Add model to the kbs
    for kb in kbs:
        path = get_regional_url(zone, f"/api/v1/account/{account_id}/models/{kb}")
        await auth._request("POST", path, data={"id": model_id})


async def list_models(auth: AsyncNucliaAuth, zone: str, account_slug: str) -> list:
    account_id = auth.get_account_id(account_slug)

    # List models
    list_models_endpoint = f"/api/v1/account/{account_id}/models"
    path = get_regional_url(zone, list_models_endpoint)
    models = await auth._request("GET", path)

    return models


async def delete_model(auth: AsyncNucliaAuth, zone: str, account_slug: str, model_id: str):
    account_id = auth.get_account_id(account_slug)

    # Delete model
    model_endpoint = f"/api/v1/account/{account_id}/model/{model_id}"
    path = get_regional_url(zone, model_endpoint)
    await auth._request("DELETE", path)


async def remove_all_models(auth: AsyncNucliaAuth, zone: str, account_slug: str):
    models = await list_models(auth, zone, account_slug)
    for model in models:
        await delete_model(auth, zone, account_slug, model["id"])
