from collections.abc import AsyncIterator
from nuclia import sdk
from nuclia.data import get_async_auth
from nuclia.sdk.auth import AsyncNucliaAuth
from nuclia_e2e.tests.conftest import ZoneConfig
from nuclia_e2e.tests.utils import as_default_generative_model_for_kb
from nuclia_e2e.tests.utils import clean_ask_test_tasks
from nuclia_e2e.tests.utils import create_ask_agent
from nuclia_e2e.tests.utils import DefaultModels
from nuclia_e2e.utils import get_async_kb_ndb_client

import os
import pytest
import uuid

TEST_ENV = os.environ.get("TEST_ENV")


# Global variable to know which tasks were created in this test
# suite so we can clean them up properly on fixture teardown
_tasks_to_delete: list[str] = []


@pytest.fixture
async def kb_id(regional_api_config: ZoneConfig) -> str:
    """
    Fixture to provide the knowledge base ID for the tests.
    """
    assert regional_api_config.global_config is not None
    return regional_api_config.permanent_kb_id


@pytest.fixture
async def zone(regional_api_config: ZoneConfig) -> str:
    """
    Fixture to provide the zone slug for the tests.
    """
    return regional_api_config.zone_slug


@pytest.fixture
def auth() -> AsyncNucliaAuth:
    """
    Fixture to provide the async Nuclia authentication object.
    """
    return get_async_auth()


@pytest.fixture(autouse=True)
async def account_id(regional_api_config: ZoneConfig, auth: AsyncNucliaAuth) -> str:
    """
    Fixture to provide the account slug for the tests.
    """
    assert regional_api_config.global_config is not None
    account_slug = regional_api_config.global_config.permanent_account_slug
    sdk.NucliaAccounts().default(account_slug)
    return auth.get_account_id(account_slug)


@pytest.fixture
async def default_models(auth: AsyncNucliaAuth, zone: str, account_id: str) -> DefaultModels:
    return DefaultModels(auth, zone, account_id)


@pytest.fixture
async def clean_tasks(kb_id: str, zone: str, auth: AsyncNucliaAuth) -> AsyncIterator[None]:
    ndb = get_async_kb_ndb_client(zone=zone, kbid=kb_id, user_token=auth._config.token)
    kb = sdk.AsyncNucliaKB()

    yield

    await clean_ask_test_tasks(kb, ndb, to_delete=_tasks_to_delete)


@pytest.fixture
async def default_model(
    kb_id: str,
    default_models: DefaultModels,
) -> AsyncIterator[str]:
    # Make sure there are no default model configs
    await default_models.remove_all()
    assert len(await default_models.list()) == 0

    # This model has been added to the vLLM server of the gke-stage-1 cluster for testing purposes
    generative_model = "chatgpt4o"

    # Configure a new default generative model config
    default_model_config_id = await default_models.add(
        generative_model=generative_model,
        model_data={
            "default_model_id": generative_model,
            "description": "Chatgpt4o with custom keys to be reused across all KBs of the account",
        },
    )

    yield f"{generative_model}/{default_model_config_id}"

    # Remove the default model config
    await default_models.remove_all()
    assert len(await default_models.list()) == 0


@pytest.mark.asyncio_cooperative
@pytest.mark.skipif(TEST_ENV != "stage", reason="This test is only for stage environment")
async def test_default_model_config_works_for_generative_and_agents(
    request: pytest.FixtureRequest,
    kb_id: str,
    zone: str,
    auth: AsyncNucliaAuth,
    default_model: str,
    clean_tasks: None,
):
    await _test_generative(kb_id, zone, auth, generative_model=default_model)
    await _test_run_resource_agents(
        kb_id, zone, auth, generative_model=default_model, generative_model_provider="openai"
    )

    async with as_default_generative_model_for_kb(kb_id, zone, auth, generative_model=default_model):
        # Do not specify the generative model -- it should use the default one
        await _test_generative(kb_id, zone, auth, generative_model=None)


async def _test_generative(kb_id: str, zone: str, auth: AsyncNucliaAuth, generative_model: str | None = None):
    # Ask a question using the new model
    ndb = get_async_kb_ndb_client(zone=zone, kbid=kb_id, user_token=auth._config.token)
    extra_params = {}
    if generative_model:
        extra_params["generative_model"] = generative_model
    answer = await sdk.AsyncNucliaSearch().ask(ndb=ndb, query="how to cook an omelette?", **extra_params)
    assert answer.answer is not None
    assert answer.status is not None
    assert answer.status == "success"
    print(f"Answer: {answer.answer}")


async def _test_run_resource_agents(
    kb_id: str, zone: str, auth: AsyncNucliaAuth, generative_model: str, generative_model_provider: str
):
    ndb = get_async_kb_ndb_client(zone=zone, kbid=kb_id, user_token=auth._config.token)

    # Configure an ingestion agent (aka task)
    unique_id = str(uuid.uuid4())
    agent_id = await create_ask_agent(
        kb_id,
        zone,
        auth,
        da_name=f"test-e2e-default-models-{unique_id}",
        question="Summarize the contents of the document in a single sentence.",
        generative_model=generative_model,
        generative_model_provider=generative_model_provider,
        destination_field_prefix=f"summary-{unique_id}",
    )

    # Add to the list
    _tasks_to_delete.append(agent_id)

    # Get a resource
    resources = await ndb.ndb.list_resources(kbid=kb_id)
    rid = resources.resources[0].id

    # Run the agent on the resource, simply make sure it doesn't fail and it returns some results
    resp = await ndb.ndb.session.post(
        f"/v1/kb/{kb_id}/resource/{rid}/run-agents", json={"agent_ids": [agent_id]}
    )
    assert str(resp.status_code).startswith("2"), resp.text
    assert len(resp.json()["results"]) > 0
