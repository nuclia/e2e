import pytest
from nuclia.sdk.predict import AsyncNucliaPredict

from regional.models import ALL_LLMS


@pytest.mark.asyncio_cooperative
@pytest.mark.parametrize("model", ALL_LLMS)
async def test_llm_rag(nua_config, model):
    np = AsyncNucliaPredict()
    generated = await np.rag(
        question="Which is the CEO of Nuclia?",
        context=[
            "Nuclia CTO is Ramon Navarro",
            "Eudald Camprubí is CEO at the same company as Ramon Navarro",
        ],
        model=model,
    )

    assert "Eudald" in generated.answer
