from nuclia.lib.nua import AsyncNuaClient
from nuclia.lib.nua_responses import ChatModel
from nuclia.sdk.predict import AsyncNucliaPredict
from nuclia_e2e.models import ALL_ENCODERS
from nuclia_e2e.models import NON_REASONING_LLMS
from nuclia_models.predict.remi import RemiRequest

import pytest


@pytest.mark.asyncio_cooperative
@pytest.mark.parametrize("model", ALL_ENCODERS.keys())
async def test_predict_sentence(nua_client: AsyncNuaClient, model):
    np = AsyncNucliaPredict()
    embed = await np.sentence(text="This is my text", model=model, nc=nua_client)
    assert embed.time > 0
    # Deprecated field (data)
    assert len(embed.data) == ALL_ENCODERS[model]
    # TODO: Check new fields 'vectors' and 'timings' that support vectorsets once SDK supports vectorsets


# TODO: Add test for predict sentence with multiple models in one request (vectorsets)


@pytest.mark.asyncio_cooperative
async def test_predict_query(nua_client: AsyncNuaClient):
    np = AsyncNucliaPredict()
    embed = await np.query(text="I really like Barcelona", nc=nua_client)
    # Semantic
    assert embed.semantic_threshold > 0
    assert len(embed.sentence.data) > 128
    # Generative
    assert embed.max_context > 0
    # Tokens
    assert embed.language == "en"
    assert len(embed.entities.tokens) > 0
    assert embed.entities.tokens[0].text == "Barcelona"


# TODO: Add test for predict rerank once SDK supports rerank


@pytest.mark.asyncio_cooperative
async def test_predict_tokens(nua_client: AsyncNuaClient):
    np = AsyncNucliaPredict()
    embed = await np.tokens(text="I love Barcelona", nc=nua_client)
    assert embed.tokens[0].text == "Barcelona"
    assert embed.tokens[0].start == 7
    assert embed.tokens[0].end == 16
    assert embed.time > 0


# Assumtion is that when they fail is either
# - server overload (ours or llm provider)
# - asyncio loop overload
# - Transient error
# For any t of hese reasons, make sense not to retry immediately
@pytest.mark.asyncio_cooperative
@pytest.mark.parametrize("model", NON_REASONING_LLMS)
async def test_predict_rephrase(nua_client: AsyncNuaClient, model):
    # Check that rephrase is working for all models
    np = AsyncNucliaPredict()

    rephrased = await np.rephrase(question="Barcelona best coffe", model=model, nc=nua_client)
    assert rephrased != "Barcelona best coffe"
    assert rephrased != ""


@pytest.mark.asyncio_cooperative
async def test_predict_remi(nua_client: AsyncNuaClient):
    np = AsyncNucliaPredict()
    results = await np.remi(
        RemiRequest(
            user_id="NUA E2E",
            question="What is the capital of France?",
            answer="Paris is the capital of france!",
            contexts=[
                "Paris is the capital of France.",
                "Berlin is the capital of Germany.",
            ],
        ),
        nc=nua_client,
    )
    assert results.answer_relevance.score >= 4

    assert results.context_relevance[0] >= 4
    assert results.groundedness[0] >= 4

    assert results.context_relevance[1] < 2
    assert results.groundedness[1] < 2


@pytest.mark.asyncio_cooperative
async def test_query_with_json_output(nua_client: AsyncNuaClient):
    np = AsyncNucliaPredict()
    response = await np.generate(
        nc=nua_client,
        text=ChatModel(
            question="how to cook an omelette?",
            user_id="e2e-test",
            json_schema={
                "name": "omelette_recipe",
                "description": "Structured answer for the instructions on how to make an omeletter",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ingredients": {
                            "type": "string",
                            "description": "Comma separated list of ingredients needed",
                        },
                        "actions": {
                            "type": "string",
                            "description": "Comma separated list of actions to complete the recipe",
                        },
                        "time": {
                            "type": "number",
                            "description": "The time duration in minutes needed to complete the recipe",
                        },
                    },
                    "required": ["ingredients", "actions", "time"],
                },
            },
        ),
        model="chatgpt-azure-4o-mini",
    )

    assert "eggs" in response.object["ingredients"]
    assert "eggs" in response.object["actions"]
    assert response.object["time"] > 0
