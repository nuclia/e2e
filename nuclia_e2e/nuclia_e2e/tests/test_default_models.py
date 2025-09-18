from collections.abc import AsyncIterator
from functools import wraps
from nuclia import get_regional_url
from nuclia import sdk
from nuclia.data import get_async_auth
from nuclia.sdk.auth import AsyncNucliaAuth
from nuclia_e2e.tests.conftest import ZoneConfig
from nuclia_e2e.tests.utils import as_kb_default_generative_model
from nuclia_e2e.tests.utils import has_generated_field
from nuclia_e2e.tests.utils import root_request
from nuclia_e2e.utils import get_async_kb_ndb_client
from nuclia_e2e.utils import wait_for
from nuclia_models.worker.proto import ApplyTo
from nuclia_models.worker.proto import AskOperation
from nuclia_models.worker.proto import Filter
from nuclia_models.worker.proto import LLMConfig
from nuclia_models.worker.proto import Operation
from nuclia_models.worker.tasks import ApplyOptions
from nuclia_models.worker.tasks import DataAugmentation
from nuclia_models.worker.tasks import TaskName
from nuclia_models.worker.tasks import TaskResponse
from typing import Any
from typing import TYPE_CHECKING

import asyncio
import os
import pytest
import random
import traceback

if TYPE_CHECKING:
    from nucliadb_models.resource import ResourceList

TEST_ENV = os.environ.get("TEST_ENV")


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
async def clean_tasks(kb_id: str, zone: str, auth: AsyncNucliaAuth) -> AsyncIterator[None]:
    ndb = get_async_kb_ndb_client(zone=zone, kbid=kb_id, user_token=auth._config.token)
    kb = sdk.AsyncNucliaKB()

    async def clean_ask_test_tasks():
        tasks = await kb.task.list(ndb=ndb)
        for task in tasks.running + tasks.done + tasks.configs:
            if task.task.name == "ask" and task.parameters.name.startswith("test-ask-default-model-config"):
                try:
                    await kb.task.delete(ndb=ndb, task_id=task.id, cleanup=True)
                except Exception:
                    print(f"Error deleting task {task.id}: {traceback.print_exc()}")

    await clean_ask_test_tasks()

    yield

    await clean_ask_test_tasks()


@pytest.fixture
async def default_model_config(
    kb_id: str, zone: str, account_id: str, auth: AsyncNucliaAuth
) -> AsyncIterator[str]:
    # Make sure there are no default model configs
    await remove_all_default_model_configs(auth, zone, account_id)
    assert len(await list_default_model_configs(auth, zone, account_id)) == 0

    # This model has been added to the vLLM server of the gke-stage-1 cluster for testing purposes
    generative_model = "chatgpt4o"

    # Configure a new default generative model config
    default_model_config_id = await add_default_model_config(
        auth,
        zone,
        account_id,
        generative_model=generative_model,
        model_data={
            "default_model_id": generative_model,
            "description": "Chatgpt4o with custom keys to be reused across all KBs of the account",
        },
    )

    yield f"{generative_model}/{default_model_config_id}"

    # Remove the default model config
    await remove_all_default_model_configs(auth, zone, account_id)
    assert len(await list_default_model_configs(auth, zone, account_id)) == 0


@pytest.mark.asyncio_cooperative
@pytest.mark.skipif(TEST_ENV != "stage", reason="This test is only for stage environment")
async def test_default_model_config_works_for_generative_and_agents(
    request: pytest.FixtureRequest,
    kb_id: str,
    zone: str,
    auth: AsyncNucliaAuth,
    default_model_config: str,
    clean_tasks: None,
):
    await _test_generative(kb_id, zone, auth, generative_model=default_model_config)
    await _test_ingestion_agents(request, kb_id, zone, auth, generative_model=default_model_config)

    async with as_kb_default_generative_model(kb_id, zone, auth, generative_model=default_model_config):
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


async def _test_ingestion_agents(
    request: pytest.FixtureRequest,
    kb_id: str,
    zone: str,
    auth: AsyncNucliaAuth,
    generative_model: str,
):
    # Create a task that summarizes the documents using the generative model config
    ndb = get_async_kb_ndb_client(zone=zone, kbid=kb_id, user_token=auth._config.token)
    kb = sdk.AsyncNucliaKB()
    destination = f"default_test_summary_{random.randint(0, 9999)}"
    tr: TaskResponse = await kb.task.start(
        ndb=ndb,
        task_name=TaskName.ASK,
        apply=ApplyOptions.ALL,
        parameters=DataAugmentation(
            name="test-ask-default-model-config",
            on=ApplyTo.FIELD,
            filter=Filter(),
            operations=[
                Operation(
                    ask=AskOperation(
                        question="What is the document about? Summarize it in a single sentence.",
                        destination=destination,
                    )
                )
            ],
            llm=LLMConfig(model=generative_model, provider="openai"),
        ),
    )
    task_id = tr.id

    rlist: ResourceList = await kb.list(ndb=ndb)
    resource_slugs = [resource.slug for resource in rlist.resources]
    assert len(resource_slugs) > 0, "No resources found in the knowledge base."

    # The expected field id for the generated field. This should match the
    # `destination` field in the AskOperation above: `da-{destination}`
    expected_field_id_prefix = f"da-{destination}"

    def resources_have_generated_fields(resource_slugs):
        @wraps(resources_have_generated_fields)
        async def condition() -> tuple[bool, Any]:
            resources_have_field = await asyncio.gather(
                *[
                    has_generated_field(ndb, kb, resource_slug, expected_field_id_prefix)
                    for resource_slug in resource_slugs
                ]
            )
            result = all(resources_have_field)
            return (result, None)

        return condition

    def logger(msg):
        print(f"{request.node.name} ::: {msg}")

    success, _ = await wait_for(
        condition=resources_have_generated_fields(resource_slugs),
        max_wait=5 * 60,  # 5 minutes
        interval=20,
        logger=logger,
    )
    assert success, f"Expected generated text fields not found in resources. task_id: {task_id}"


async def add_default_model_config(
    auth: AsyncNucliaAuth,
    zone: str,
    account_id: str,
    generative_model: str,
    model_data: dict,
) -> str:
    if "default_model_id" not in model_data:
        model_data["default_model_id"] = generative_model
    # Add model to the account
    path = get_regional_url(zone, f"/api/v1/account/{account_id}/default_models")
    response = await root_request(auth, "POST", path, data=model_data)
    assert response is not None
    model_id = response["id"]
    return model_id


async def list_default_model_configs(auth: AsyncNucliaAuth, zone: str, account_id: str) -> list:
    path = get_regional_url(zone, f"/api/v1/account/{account_id}/default_models")
    models = await root_request(auth, "GET", path)
    assert models is not None
    assert isinstance(models, list)
    return models


async def delete_default_model_config(auth: AsyncNucliaAuth, zone: str, account_id: str, model_id: str):
    path = get_regional_url(zone, f"/api/v1/account/{account_id}/default_model/{model_id}")
    await root_request(auth, "DELETE", path)


async def remove_all_default_model_configs(auth: AsyncNucliaAuth, zone: str, account_id: str):
    models = await list_default_model_configs(auth, zone, account_id)
    for model in models:
        await delete_default_model_config(auth, zone, account_id, model["id"])
