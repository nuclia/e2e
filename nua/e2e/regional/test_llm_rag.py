import pytest
from nuclia.sdk.predict import NucliaPredict

from regional.models import ALL_LLMS


@pytest.mark.parametrize("model", ALL_LLMS)
def test_llm_rag(nua_config, model):
    np = NucliaPredict()
    generated = np.rag(
        question="Which is the CEO of Nuclia?",
        context=[
            "Nuclia CTO is Ramon Navarro",
            "Eudald Camprubí is CEO at the same company as Ramon Navarro",
        ],
        model=model,
    )

    assert "Eudald" in generated.answer
