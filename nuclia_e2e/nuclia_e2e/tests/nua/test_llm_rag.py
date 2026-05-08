from nuclia.lib.nua import AsyncNuaClient
from nuclia.sdk.predict import AsyncNucliaPredict
from nuclia_e2e.models import ALL_LLMS
from nuclia_e2e.models import model_zone_check
from nuclia_e2e.tests.conftest import ZoneConfig
from nuclia_e2e.utils import make_retry_async
from nuclia_e2e.utils import skip_on_provider_transient_error

import pytest


# Assumtion is that when they fail is either
# - server overload (ours or llm provider)
# - asyncio loop overload
# - Transient error
# For any t of hese reasons, make sense not to retry immediately
@pytest.mark.asyncio_cooperative
@pytest.mark.parametrize("model", ALL_LLMS)
async def test_llm_rag(nua_client: AsyncNuaClient, model: str, regional_api_config: ZoneConfig):
    model_zone_check(model, regional_api_config.name)
    np = AsyncNucliaPredict()

    @make_retry_async(attempts=3, delay=10, exceptions=(AssertionError,))
    async def retryable_block():
        generated = await np.rag(
            question="Which is the CEO of Nuclia?",
            context=[
                "Nuclia CTO is Ramon Navarro",
                "Eudald Camprubí is CEO at the same company as Ramon Navarro",
            ],
            model=model,
            nc=nua_client,
        )
        assert "Eudald" in generated.answer

    with skip_on_provider_transient_error():
        await retryable_block()
