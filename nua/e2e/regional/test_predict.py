from nuclia.sdk.predict import NucliaPredict


def test_predict_sentence_multilingual_2023_02_21(nua_config):
    np = NucliaPredict()
    embed = np.sentence(text="This is my text", model="multilingual-2024-05-06")
    assert embed.time > 0
    assert len(embed.data) == 1024


def test_predict_sentence_multilingual_2023_08_16(nua_config):
    np = NucliaPredict()
    embed = np.sentence(text="This is my text", model="multilingual-2023-08-16")
    assert embed.time > 0
    assert len(embed.data) == 1024


def test_predict_sentence_multilingual_en(nua_config):
    np = NucliaPredict()
    embed = np.sentence(text="This is my text", model="en-2024-04-24")
    assert embed.time > 0
    assert len(embed.data) == 768


def test_predict_entity_multilingual_2023_02_21(nua_config):
    np = NucliaPredict()
    embed = np.tokens(text="I'm flying to Barcelona", model="multilingual")
    assert embed.time > 0
    assert len(embed.tokens) == 1


def test_predict_query_multilingual_multilingual(nua_config):
    np = NucliaPredict()
    embed = np.query(text="This is my text")
    assert len(embed.sentence.data) == 1024
