from nuclia.sdk.auth import AsyncNucliaAuth
from nuclia_e2e.tests.utils import as_default_generative_model_for_kb
from nuclia_e2e.tests.utils import CustomModels
from nuclia_e2e.tests.utils import DefaultModels
from nuclia_e2e.tests.utils import run_generative_test
from nuclia_e2e.tests.utils import run_resource_agents_test

import os
import pytest

TEST_ENV = os.environ.get("TEST_ENV")


@pytest.fixture
async def custom_models(auth: AsyncNucliaAuth, zone: str, account_id: str) -> CustomModels:
    return CustomModels(auth, zone, account_id)


@pytest.fixture
async def custom_model(kb_id: str, custom_models: CustomModels) -> str:
    # This model has been added to the vLLM server of the gke-stage-1 cluster for testing purposes
    model_location = "custom:qwen3-8b"
    custom_list = await custom_models.list()
    try:
        next(m for m in custom_list if m["location"] == model_location)
    except StopIteration:
        # Configure a new custom generative model
        await custom_models.add(
            model_data={
                "description": "test_model",
                "location": model_location,
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
    return model_location


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


@pytest.fixture
async def default_model_with_bedrock_assume_role():
    # This has been manually setup in the testing account
    return "aws-claude-3-7-sonnet/6cbb8b45-2e0b-4f25-bb42-d87a9c209f4e"


@pytest.mark.asyncio_cooperative
@pytest.mark.skipif(TEST_ENV != "stage", reason="This test is only for stage environment")
async def test_account_models(
    request: pytest.FixtureRequest,
    kb_id: str,
    zone: str,
    auth: AsyncNucliaAuth,
    custom_model: str,
    default_model: str,
    default_model_with_bedrock_assume_role: str,
    clean_tasks: None,
):
    """
    All tests related to account models should go here. We can't really run then in parallel because
    they change the default model of the KB.
    """

    # Default model tests
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

    # Default model with bedrock assume role tests
    async with as_default_generative_model_for_kb(
        kb_id, zone, auth, generative_model=default_model_with_bedrock_assume_role
    ):
        await run_generative_test(kb_id, zone, auth, generative_model=None)
        await run_generative_test(kb_id, zone, auth, generative_model=default_model_with_bedrock_assume_role)
        await run_resource_agents_test(
            kb_id,
            zone,
            auth,
            generative_model=default_model_with_bedrock_assume_role,
            generative_model_provider="anthropic",
            da_name_prefix="test-e2e-bedrock-assume-role-",
            destination_field_prefix="summary_",
        )

    # Custom model tests
    async with as_default_generative_model_for_kb(kb_id, zone, auth, custom_model):
        await run_generative_test(kb_id, zone, auth, generative_model=None)
        await run_generative_test(kb_id, zone, auth, generative_model=custom_model)
        await run_resource_agents_test(
            kb_id,
            zone,
            auth,
            generative_model=custom_model,
            generative_model_provider="custom",
            da_name_prefix="test-e2e-custom-models-",
            destination_field_prefix="summary_",
        )
