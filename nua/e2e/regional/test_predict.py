import pytest
from nuclia.sdk.predict import AsyncNucliaPredict

from regional.models import ALL_ENCODERS, ALL_LLMS
from nuclia_models.predict.remi import RemiRequest


@pytest.mark.asyncio_cooperative
@pytest.mark.parametrize("model", ALL_ENCODERS.keys())
async def test_predict_sentence(nua_config, model):
    np = AsyncNucliaPredict()
    embed = await np.sentence(text="This is my text", model=model)
    assert embed.time > 0
    # Deprecated field (data)
    assert len(embed.data) == ALL_ENCODERS[model]
    # TODO: Check new fields 'vectors' and 'timings' that support vectorsets once SDK supports vectorsets


# TODO: Add test for predict sentence with multiple models in one request (vectorsets)


@pytest.mark.asyncio_cooperative
async def test_predict_query(nua_config):
    np = AsyncNucliaPredict()
    embed = await np.query(text="I love Barcelona")
    # Semantic
    assert embed.semantic_threshold > 0
    assert len(embed.sentence.data) > 128
    # Generative
    assert embed.max_context > 0
    # Tokens
    assert embed.language == "en"
    assert (
        len(embed.entities.tokens) > 0 and embed.entities.tokens[0].text == "Barcelona"
    )


# TODO: Add test for predict rerank once SDK supports rerank


@pytest.mark.asyncio_cooperative
async def test_predict_tokens(nua_config):
    np = AsyncNucliaPredict()
    embed = await np.tokens(text="I love Barcelona")
    assert embed.tokens[0].text == "Barcelona"
    assert embed.tokens[0].start == 7
    assert embed.tokens[0].end == 16
    assert embed.time > 0


@pytest.mark.asyncio_cooperative
@pytest.mark.parametrize("model", ALL_LLMS)
async def test_predict_rephrase(nua_config, model):
    # Check that rephrase is working for all models
    np = AsyncNucliaPredict()
    # TODO: Test that custom rephrase prompt works once SDK supports it
    rephrased = await np.rephrase(question="Barcelona best coffe", model=model)
    assert rephrased != "Barcelona best coffe" and rephrased != ""


@pytest.mark.asyncio_cooperative
async def test_predict_remi(nua_config):
    # Check that rephrase is working for all models
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
        )
    )
    assert results.answer_relevance.score >= 4

    assert results.context_relevance[0] >= 4
    assert results.groundedness[0] >= 4

    assert results.context_relevance[1] < 2
    assert results.groundedness[1] < 2
