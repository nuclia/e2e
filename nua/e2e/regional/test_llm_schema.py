from nuclia.sdk.predict import NucliaPredict


def test_llm_schema_nua(nua_config):
    np = NucliaPredict()
    config = np.schema()

    assert len(config.ner_model.options) == 1
    assert len(config.generative_model.options) >= 5


def test_llm_schema_kbid(nua_config):
    np = NucliaPredict()
    config = np.schema("fake_kbid")
    assert len(config.ner_model.options) == 1
    assert len(config.generative_model.options) >= 5
