from collections.abc import AsyncIterator
from functools import wraps
from nuclia import get_regional_url
from nuclia import sdk
from nuclia.data import get_async_auth
from nuclia.lib.kb import AsyncNucliaDBClient
from nuclia.sdk.auth import AsyncNucliaAuth
from nuclia_e2e.tests.conftest import ZoneConfig
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
from nucliadb_sdk.v2.exceptions import NotFoundError
from typing import Any
from typing import TYPE_CHECKING

import asyncio
import os
import pytest

if TYPE_CHECKING:
    from nucliadb_models.resource import ResourceList

TEST_ENV = os.environ.get("TEST_ENV")


@pytest.fixture
async def custom_model(request: pytest.FixtureRequest, regional_api_config: ZoneConfig) -> AsyncIterator[str]:
    kb_id = regional_api_config.permanent_kb_id
    zone = regional_api_config.zone_slug
    assert regional_api_config.global_config is not None
    account_slug = regional_api_config.global_config.permanent_account_slug

    sdk.NucliaAccounts().default(account_slug)

    auth = get_async_auth()
    account_id = auth.get_account_id(account_slug)

    # Make sure there are no custom models configured
    await remove_all_models(auth, zone, account_id)
    assert len(await list_models(auth, zone, account_id)) == 0

    # This model has been added to the vLLM server of the gke-stage-1 cluster for testing purposes
    model = "openai_compat:qwen3-8b"

    # Configure a new custom generative model
    await add_model(
        auth,
        zone,
        account_id,
        model_data={
            "description": "test_model",
            "location": model,
            "model_types": ["GENERATIVE"],
            "model_type": "GENERATIVE",
            "openai_compat": {
                "url": "http://vllm-stack-router-service.vllm-stack.svc.cluster.local/v1",
                "model_id": "Qwen3-8B",
                "tokenizer": 0,  # Unspecified tokenizer
                "key": "",  # No key needed for this model
                "model_features": {
                    "vision": False,
                    "tool_use": True,
                },
                "generation_config": {
                    "default_max_completion_tokens": 800,
                    "max_input_tokens": 32_768 - 800,
                },
            },
        },
        kbs=[kb_id],
    )

    yield model

    # Remove the custom model
    await remove_all_models(auth, zone, account_id)
    assert len(await list_models(auth, zone, account_id)) == 0


@pytest.mark.asyncio_cooperative
@pytest.mark.skipif(TEST_ENV != "stage", reason="This test is only for stage environment")
async def test_generative(request: pytest.FixtureRequest, regional_api_config: ZoneConfig, custom_model: str):
    kb_id = regional_api_config.permanent_kb_id
    zone = regional_api_config.zone_slug
    assert regional_api_config.global_config is not None
    account_slug = regional_api_config.global_config.permanent_account_slug

    sdk.NucliaAccounts().default(account_slug)

    auth = get_async_auth()

    # Ask a question using the new model
    ndb = get_async_kb_ndb_client(zone=zone, kbid=kb_id, user_token=auth._config.token)
    answer = await sdk.AsyncNucliaSearch().ask(
        ndb=ndb,
        query="how to cook an omelette?",
        generative_model=custom_model,
    )
    assert answer.answer is not None
    assert answer.status is not None
    assert answer.status == "success"
    print(f"Answer: {answer.answer}")


@pytest.mark.asyncio_cooperative
@pytest.mark.skipif(TEST_ENV != "stage", reason="This test is only for stage environment")
async def test_ingestion_agents(
    request: pytest.FixtureRequest, regional_api_config: ZoneConfig, custom_model: str
):
    kb_id = regional_api_config.permanent_kb_id
    zone = regional_api_config.zone_slug
    assert regional_api_config.global_config is not None
    account_slug = regional_api_config.global_config.permanent_account_slug

    sdk.NucliaAccounts().default(account_slug)

    auth = get_async_auth()

    # Create a task that summarizes the documents using the custom model
    ndb = get_async_kb_ndb_client(zone=zone, kbid=kb_id, user_token=auth._config.token)
    kb = sdk.AsyncNucliaKB()
    destination = "customsummary2"
    tr: TaskResponse = await kb.task.start(
        ndb=ndb,
        task_name=TaskName.ASK,
        apply=ApplyOptions.ALL,
        parameters=DataAugmentation(
            name="test-ask-custom-model",
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
            llm=LLMConfig(model=custom_model, provider="openai_compat"),
        ),
    )
    task_id = tr.id

    rlist: ResourceList = await kb.list(ndb=ndb)
    resource_slugs = [resource.slug for resource in rlist.resources]

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

    try:
        success, _ = await wait_for(
            condition=resources_have_generated_fields(resource_slugs),
            max_wait=5 * 60,  # 5 minutes
            interval=20,
            logger=logger,
        )
        assert success, f"Expected generated text fields not found in resources. task_id: {task_id}"
    finally:
        await kb.task.delete(
            ndb=ndb,
            task_id=task_id,
            cleanup=True,
        )


async def has_generated_field(
    ndb: AsyncNucliaDBClient,
    kb: sdk.AsyncNucliaKB,
    resource_slug: str,
    expected_field_id_prefix: str,
) -> bool:
    """
    Check if the resource has the extracted text for the generated field.
    """
    try:
        res = await kb.resource.get(slug=resource_slug, show=["values", "extracted"], ndb=ndb)
    except NotFoundError:
        # some resource may still be missing from nucliadb, let's wait more
        return False
    try:
        for fid, data in res.data.texts.items():
            if fid.startswith(expected_field_id_prefix) and data.extracted.text.text is not None:
                return True
    except (TypeError, AttributeError):
        # If the resource does not have the expected structure, let's wait more
        return False
    else:
        # If we reach here, it means the field was not found
        return False


async def add_model(
    auth: AsyncNucliaAuth,
    zone: str,
    account_id: str,
    model_data: dict,
    kbs: list[str],
):
    # Add model to the account
    path = get_regional_url(zone, f"/api/v1/account/{account_id}/models")
    response = await root_request(auth, "POST", path, data=model_data)
    assert response is not None
    model_id = response["id"]

    # Add model to the kbs
    for kb in kbs:
        path = get_regional_url(zone, f"/api/v1/account/{account_id}/models/{kb}")
        await root_request(auth, "POST", path, data={"id": model_id})


async def list_models(auth: AsyncNucliaAuth, zone: str, account_id: str) -> list:
    path = get_regional_url(zone, f"/api/v1/account/{account_id}/models")
    models = await root_request(auth, "GET", path)
    assert models is not None
    assert isinstance(models, list)
    return models


async def delete_model(auth: AsyncNucliaAuth, zone: str, account_id: str, model_id: str):
    path = get_regional_url(zone, f"/api/v1/account/{account_id}/model/{model_id}")
    await root_request(auth, "DELETE", path)


async def remove_all_models(auth: AsyncNucliaAuth, zone: str, account_id: str):
    models = await list_models(auth, zone, account_id)
    for model in models:
        await delete_model(auth, zone, account_id, model["model_id"])


async def root_request(
    auth: AsyncNucliaAuth,
    method: str,
    path: str,
    data: dict | None = None,
    headers: dict | None = None,
) -> dict | None:
    """
    Make a request to the API with root credentials. This is not currently supported by the SDK,
    so we need to do it manually.
    """
    headers = headers or {}
    stage_root_pat_token = os.environ["STAGE_ROOT_PAT_TOKEN"]
    headers["Authorization"] = f"Bearer {stage_root_pat_token}"
    resp = await auth.client.request(
        method,
        path,
        json=data,
        headers=headers,
    )
    if resp.status_code == 204:
        return None
    if resp.status_code >= 200 and resp.status_code < 300:
        return resp.json()
    if resp.status_code >= 300 and resp.status_code < 400:
        return None
    raise Exception({"status": resp.status_code, "message": resp.text})  # noqa: TRY002
