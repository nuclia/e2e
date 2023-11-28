from nuclia.sdk.predict import NucliaPredict
import pytest
import time


@pytest.mark.benchmark(
    group="predict",
    min_time=0.1,
    max_time=0.5,
    min_rounds=5,
    timer=time.time,
    disable_gc=True,
    warmup=False,
)
def test_predict_sentence_multilingual_2023_02_21(nua_config, benchmark):
    np = NucliaPredict()
    embed = benchmark(
        np.sentence, text="This is my text", model="multilingual-2023-02-21"
    )
    assert embed.time > 0
    assert len(embed.data) == 768


@pytest.mark.benchmark(
    group="predict",
    min_time=0.1,
    max_time=0.5,
    min_rounds=5,
    timer=time.time,
    disable_gc=True,
    warmup=False,
)
def test_predict_sentence_multilingual_2023_08_16(nua_config, benchmark):
    np = NucliaPredict()
    embed = benchmark(
        np.sentence, text="This is my text", model="multilingual-2023-08-16"
    )
    assert embed.time > 0
    assert len(embed.data) == 1024


@pytest.mark.benchmark(
    group="predict",
    min_time=0.1,
    max_time=0.5,
    min_rounds=5,
    timer=time.time,
    disable_gc=True,
    warmup=False,
)
def test_predict_sentence_multilingual_multilingual(nua_config, benchmark):
    np = NucliaPredict()
    embed = benchmark(np.sentence, text="This is my text", model="multilingual")
    assert embed.time > 0
    assert len(embed.data) == 768


@pytest.mark.benchmark(
    group="predict",
    min_time=0.1,
    max_time=0.5,
    min_rounds=5,
    timer=time.time,
    disable_gc=True,
    warmup=False,
)
def test_predict_sentence_multilingual_en(nua_config, benchmark):
    np = NucliaPredict()
    embed = benchmark(np.sentence, text="This is my text", model="en")
    assert embed.time > 0
    assert len(embed.data) == 384


@pytest.mark.benchmark(
    group="predict",
    min_time=0.1,
    max_time=0.5,
    min_rounds=5,
    timer=time.time,
    disable_gc=True,
    warmup=False,
)
def test_predict_entity_multilingual_2023_02_21(nua_config, benchmark):
    np = NucliaPredict()
    embed = benchmark(
        np.tokens, text="I'm flying to Barcelona", model="multilingual-2023-02-21"
    )
    assert embed.time > 0
    assert len(embed.tokens) == 1
