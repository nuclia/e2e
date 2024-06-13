from nuclia.sdk.predict import NucliaPredict
import pytest
from nuclia.exceptions import NuaAPIException
from nuclia.lib.nua_responses import LearningConfigurationCreation


def test_llm_config_nua(nua_config):
    np = NucliaPredict()

    try:
        np.del_config("kbid")
    except NuaAPIException:
        pass

    with pytest.raises(NuaAPIException):
        config = np.config("kbid")

    lcc = LearningConfigurationCreation()
    np.set_config("kbid", lcc)

    config = np.config("kbid")

    assert config.resource_labelers_models is None
    assert config.ner_model == "multilingual"
    assert config.generative_model == "chatgpt-azure"
