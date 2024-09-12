import pytest
from nuclia.sdk.predict import NucliaPredict

from regional.models import ALL_LLMS


@pytest.mark.parametrize("model", ALL_LLMS)
def test_llm_generate(nua_config, model):
    np = NucliaPredict()
    generated = np.generate("Which is the capital of Catalonia?", model=model)
    assert "Barcelona" in generated.answer
