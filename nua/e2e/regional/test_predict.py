import pytest
from nuclia.sdk.predict import NucliaPredict

from regional.models import ALL_ENCODERS, ALL_LLMS


@pytest.mark.parametrize("model", ALL_ENCODERS.keys())
def test_predict_sentence(nua_config, model):
    np = NucliaPredict()
    embed = np.sentence(text="This is my text", model=model)
    assert embed.time > 0
    # Deprecated field (data)
    assert len(embed.data) == ALL_ENCODERS[model]
    # TODO: Check new fields 'vectors' and 'timings' that support vectorsets once SDK supports vectorsets


# TODO: Add test for predict sentence with multiple models in one request (vectorsets)


def test_predict_query(nua_config):
    np = NucliaPredict()
    embed = np.query(text="I love Barcelona")
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


def test_predict_tokens(nua_config):
    np = NucliaPredict()
    embed = np.tokens(text="I love Barcelona")
    assert embed.tokens[0].text == "Barcelona"
    assert embed.tokens[0].start == 7
    assert embed.tokens[0].end == 16
    assert embed.time > 0


@pytest.mark.parametrize("model", ALL_LLMS)
def test_predict_rephrase(nua_config, model):
    # Check that rephrase is working for all models
    np = NucliaPredict()
    # TODO: Test that custom rephrase prompt works once SDK supports it
    rephrased = np.rephrase(question="Barcelona best coffe", model=model)
    assert "?" in rephrased
