from nuclia.sdk.predict import NucliaPredict


def test_predict_sentence_multilingual_2023_02_21(nua_config):
    np = NucliaPredict()
    embed = np.sentence(text="This is my text", model="multilingual-2023-02-21")
    assert embed.time > 0
    assert len(embed.data) == 768


def test_predict_sentence_multilingual_2023_08_16(nua_config):
    np = NucliaPredict()
    embed = np.sentence(text="This is my text", model="multilingual-2023-08-16")
    assert embed.time > 0
    assert len(embed.data) == 1024


def test_predict_sentence_multilingual_en(nua_config):
    np = NucliaPredict()
    embed = np.sentence(text="This is my text", model="en")
    assert embed.time > 0
    assert len(embed.data) == 384


def test_predict_entity_multilingual_2023_02_21(nua_config):
    np = NucliaPredict()
    embed = np.tokens(text="I'm flying to Barcelona", model="multilingual")
    assert embed.time > 0
    assert len(embed.tokens) == 1
