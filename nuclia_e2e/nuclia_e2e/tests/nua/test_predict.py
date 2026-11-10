from nuclia.lib.nua import AsyncNuaClient
from nuclia.lib.nua_responses import ChatModel
from nuclia.sdk.predict import AsyncNucliaPredict
from nuclia_e2e.models import ALL_DECISION_MODELS
from nuclia_e2e.models import ALL_ENCODERS
from nuclia_e2e.models import model_zone_check
from nuclia_e2e.models import REPHRASE_TEST_LLMS
from nuclia_e2e.tests.conftest import ZoneConfig
from nuclia_e2e.utils import skip_on_provider_transient_error
from nuclia_models.predict.decisions import ChoiceAnswer
from nuclia_models.predict.decisions import DecisionRequest
from nuclia_models.predict.decisions import NoulAnswer
from nuclia_models.predict.decisions import OpenAIChoiceAnswer
from nuclia_models.predict.decisions import OpenAIDecisionRequest
from nuclia_models.predict.decisions import OpenAIPredicateAnswer
from nuclia_models.predict.decisions import OpenAIScoreAnswer
from nuclia_models.predict.decisions import ScoreAnswer
from nuclia_models.predict.remi import RemiRequest

import pytest

NO_CONSUMPTION_MODELS = ["progress-decision-1.0"]


def assert_decision_usage_and_consumption(response):
    assert response.usage.input_tokens > 0
    assert response.usage.output_tokens >= 0
    assert response.usage.total_tokens == response.usage.input_tokens + response.usage.output_tokens

    if response.model not in NO_CONSUMPTION_MODELS:
        assert response.consumption is not None
        normalized = response.consumption.normalized_tokens
        assert normalized.input >= 0
        assert normalized.output >= 0
        assert normalized.image >= 0


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
@pytest.mark.parametrize("model", REPHRASE_TEST_LLMS)
async def test_predict_rephrase(nua_client: AsyncNuaClient, model, regional_api_config: ZoneConfig):
    model_zone_check(model, regional_api_config.name)
    # Check that rephrase is working for all models
    np = AsyncNucliaPredict()

    with skip_on_provider_transient_error():
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
@pytest.mark.parametrize("model", ALL_DECISION_MODELS.keys())
async def test_predict_decision_system_one_account(
    nua_client: AsyncNuaClient,
    regional_api_config: ZoneConfig,
    model: str,
):
    model_zone_check(model, regional_api_config.name, ALL_DECISION_MODELS)
    request = DecisionRequest.model_validate(
        {
            "model": model,
            "state": "Paris is the capital of France.",
            "questions": {
                "is_correct": {
                    "type": "noul",
                    "instructions": "Is the statement factually correct?",
                },
                "capital": {
                    "type": "choice",
                    "instructions": "Which city does the statement identify as the capital of France?",
                    "criteria": {
                        "paris": "Paris",
                        "berlin": "Berlin",
                    },
                },
                "accuracy": {
                    "type": "score",
                    "instructions": "Score the factual accuracy of the statement.",
                    "criteria": [
                        "The statement is factually incorrect.",
                        "The statement is factually correct.",
                    ],
                },
            },
        }
    )

    predict = AsyncNucliaPredict()
    with skip_on_provider_transient_error():
        response = await predict.decision_system_one(
            request,
            show_consumption=True,
            nc=nua_client,
        )
    assert response.model == model
    assert response.model == model

    noul = response.answers["is_correct"]
    assert isinstance(noul, NoulAnswer)
    assert noul.noul > 0.5

    choice = response.answers["capital"]
    assert isinstance(choice, ChoiceAnswer)
    assert choice.choice == "paris"
    assert choice.probabilities["paris"] > choice.probabilities["berlin"]

    score = response.answers["accuracy"]
    assert isinstance(score, ScoreAnswer)
    assert score.score > 0.5

    assert_decision_usage_and_consumption(response)


@pytest.mark.asyncio_cooperative
@pytest.mark.parametrize("model", ALL_DECISION_MODELS.keys())
async def test_predict_decision_openai_account(
    nua_client: AsyncNuaClient,
    regional_api_config: ZoneConfig,
    model: str,
):
    model_zone_check(model, regional_api_config.name, ALL_DECISION_MODELS)
    request = OpenAIDecisionRequest.model_validate(
        {
            "model": model,
            "input": "Paris is the capital of France.",
            "questions": [
                {
                    "type": "predicate",
                    "name": "is_correct",
                    "instructions": "Is the statement factually correct?",
                },
                {
                    "type": "choice",
                    "name": "correct",
                    "instructions": "Is the statement correct?",
                    "choices": [
                        {"value": False, "description": "The statement is incorrect."},
                        {"value": True, "description": "The statement is correct."},
                    ],
                },
                {
                    "type": "score",
                    "name": "accuracy",
                    "instructions": "Score the factual accuracy of the statement.",
                    "levels": [
                        {"label": "incorrect", "description": "The statement is incorrect."},
                        {"label": "correct", "description": "The statement is correct."},
                    ],
                },
            ],
        }
    )

    predict = AsyncNucliaPredict()
    with skip_on_provider_transient_error():
        response = await predict.decision(
            request,
            show_consumption=True,
            nc=nua_client,
        )

    assert response.model == model
    answers = {answer.name: answer for answer in response.answers}

    predicate = answers["is_correct"]
    assert isinstance(predicate, OpenAIPredicateAnswer)
    assert predicate.probability > 0.5

    choice = answers["correct"]
    assert isinstance(choice, OpenAIChoiceAnswer)
    assert choice.choice is True
    true_probability = next(item.probability for item in choice.probabilities if item.value is True)
    false_probability = next(item.probability for item in choice.probabilities if item.value is False)
    assert true_probability > false_probability

    score = answers["accuracy"]
    assert isinstance(score, OpenAIScoreAnswer)
    assert score.score > 0.5

    assert_decision_usage_and_consumption(response)


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
        model="chatgpt-azure-5.6-luna",
    )

    assert "eggs" in response.object["ingredients"]
    assert "eggs" in response.object["actions"]
    assert response.object["time"] > 0
