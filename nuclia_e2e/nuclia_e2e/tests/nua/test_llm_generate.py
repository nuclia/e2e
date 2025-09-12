from nuclia.lib.nua import AsyncNuaClient
from nuclia.sdk.predict import AsyncNucliaPredict
from nuclia_e2e.models import ALL_LLMS
from nuclia_e2e.models import model_zone_check
from nuclia_e2e.tests.conftest import ZoneConfig
from nuclia_e2e.utils import make_retry_async

import pytest


# We use a retry wrapper function instead of a context manager
# because async context managers yield inside a retry loop,
# which leads to runtime errors when retries stop unexpectedly.
# Also, flaky plugin is not compatible with asyncio_cooperative
@pytest.mark.asyncio_cooperative
@pytest.mark.parametrize("model", ALL_LLMS)
async def test_llm_generate(nua_client: AsyncNuaClient, model: str, regional_api_config: ZoneConfig):
    model_zone_check(model, regional_api_config.name)
    np = AsyncNucliaPredict()

    @make_retry_async(attempts=3, delay=10, exceptions=(AssertionError,))
    async def test_nua_generate():
        generated = await np.generate("Which is the capital of Catalonia?", model=model, nc=nua_client)
        assert "Barcelona" in generated.answer

    await test_nua_generate()
