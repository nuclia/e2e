from nuclia.sdk.auth import AsyncNucliaAuth
from nuclia_e2e.tests.utils import as_default_generative_model_for_kb
from nuclia_e2e.tests.utils import DefaultModels
from nuclia_e2e.tests.utils import run_generative_test
from nuclia_e2e.tests.utils import run_resource_agents_test

import os
import pytest

TEST_ENV = os.environ.get("TEST_ENV")


@pytest.fixture
async def default_models(auth: AsyncNucliaAuth, zone: str, account_id: str) -> DefaultModels:
    return DefaultModels(auth, zone, account_id)


@pytest.fixture
async def default_model(
    kb_id: str,
    default_models: DefaultModels,
) -> str:
    generative_model = "chatgpt4o"
    default_list = await default_models.list()
    try:
        # If there is already one, return it
        found = next(
            mo for mo in default_list if (mo.get("default_model_id", "")).startswith(generative_model)
        )
        config_id = found["id"]
    except StopIteration:
        # Otherwise, configure a new default generative model config
        config_id = await default_models.add(
            generative_model=generative_model,
            model_data={
                "default_model_id": generative_model,
                "description": "Chatgpt4o with custom keys to be reused across all KBs of the account",
            },
        )
    return f"{generative_model}/{config_id}"


@pytest.mark.asyncio_cooperative
@pytest.mark.skipif(TEST_ENV != "stage", reason="This test is only for stage environment")
async def test_default_model_works_for_generative_and_agents(
    request: pytest.FixtureRequest,
    kb_id: str,
    zone: str,
    auth: AsyncNucliaAuth,
    default_model: str,
    clean_tasks: None,
):
    async with as_default_generative_model_for_kb(kb_id, zone, auth, generative_model=default_model):
        await run_generative_test(kb_id, zone, auth, generative_model=None)
        await run_generative_test(kb_id, zone, auth, generative_model=default_model)
        await run_resource_agents_test(
            kb_id,
            zone,
            auth,
            generative_model=default_model,
            generative_model_provider="openai",
            da_name_prefix="test-e2e-default-models-",
            destination_field_prefix="summary_",
        )
