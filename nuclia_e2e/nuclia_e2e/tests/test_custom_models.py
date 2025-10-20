from collections.abc import AsyncIterator
from nuclia import sdk
from nuclia.sdk.auth import AsyncNucliaAuth
from nuclia_e2e.tests.utils import as_default_generative_model_for_kb
from nuclia_e2e.tests.utils import clean_ask_test_tasks
from nuclia_e2e.tests.utils import create_ask_agent
from nuclia_e2e.tests.utils import CustomModels
from nuclia_e2e.utils import get_async_kb_ndb_client

import os
import pytest
import uuid

TEST_ENV = os.environ.get("TEST_ENV")

# Global variable to know which tasks were created in this test
# suite so we can clean them up properly on fixture teardown
_tasks_to_delete: list[str] = []


@pytest.fixture
async def clean_tasks(kb_id: str, zone: str, auth: AsyncNucliaAuth) -> AsyncIterator[None]:
    ndb = get_async_kb_ndb_client(zone=zone, kbid=kb_id, user_token=auth._config.token)
    kb = sdk.AsyncNucliaKB()

    yield

    await clean_ask_test_tasks(kb, ndb, to_delete=_tasks_to_delete)


@pytest.fixture
async def custom_models(auth: AsyncNucliaAuth, zone: str, account_id: str) -> CustomModels:
    return CustomModels(auth, zone, account_id)


@pytest.fixture
async def custom_model(kb_id: str, custom_models: CustomModels) -> str:
    # Make sure there are no custom models configured
    await custom_models.remove_all()
    assert len(await custom_models.list()) == 0

    # This model has been added to the vLLM server of the gke-stage-1 cluster for testing purposes
    model = "custom:qwen3-8b"

    # Configure a new custom generative model
    await custom_models.add(
        model_data={
            "description": "test_model",
            "location": model,
            "model_types": ["GENERATIVE", "SUMMARY"],
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

    return model


@pytest.mark.asyncio_cooperative
@pytest.mark.skipif(TEST_ENV != "stage", reason="This test is only for stage environment")
async def test_custom_models_work_for_generative_and_agents(
    request: pytest.FixtureRequest,
    kb_id: str,
    zone: str,
    auth: AsyncNucliaAuth,
    custom_model: str,
    clean_tasks: None,
):
    async with as_default_generative_model_for_kb(kb_id, zone, auth, custom_model):
        await _test_generative(kb_id, zone, auth, generative_model=None)
        await _test_generative(kb_id, zone, auth, generative_model=custom_model)
        await _test_run_resource_agents(
            kb_id, zone, auth, generative_model=custom_model, generative_model_provider="custom"
        )


async def _test_generative(kb_id: str, zone: str, auth: AsyncNucliaAuth, generative_model: str | None = None):
    # Send an ask request with the model (if specified) or with the default configured model in the kb.
    ndb = get_async_kb_ndb_client(zone=zone, kbid=kb_id, user_token=auth._config.token)
    extra_params = {}
    if generative_model:
        extra_params["generative_model"] = generative_model
    answer = await sdk.AsyncNucliaSearch().ask(
        ndb=ndb, query="how to cook an omelette? Answer in less than 200 words please.", **extra_params
    )
    assert answer.answer is not None
    assert answer.status is not None
    assert answer.status == "success"
    print(f"Answer: {answer.answer}")


async def _test_run_resource_agents(
    kb_id: str, zone: str, auth: AsyncNucliaAuth, generative_model: str, generative_model_provider: str
):
    ndb = get_async_kb_ndb_client(zone=zone, kbid=kb_id, user_token=auth._config.token)

    # Configure an ingestion agent (aka task)
    unique_id = uuid.uuid4().hex
    agent_id = await create_ask_agent(
        kb_id,
        zone,
        auth,
        da_name=f"test-e2e-custom-models-{unique_id}",
        question="Summarize the contents of the document in a single sentence.",
        generative_model=generative_model,
        generative_model_provider=generative_model_provider,
        destination_field_prefix=f"summary_{unique_id}",
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
