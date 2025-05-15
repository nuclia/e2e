from nuclia.lib.nua import AsyncNuaClient
from nuclia.sdk.predict import AsyncNucliaPredict
from nuclia_e2e.models import ALL_LLMS

import pytest
from nuclia_e2e.utils import make_retry_async


# We use a retry wrapper function instead of a context manager
# because async context managers yield inside a retry loop,
# which leads to runtime errors when retries stop unexpectedly.
# Also, flaky plugin is not compatible with asyncio_cooperative
@pytest.mark.asyncio_cooperative
@pytest.mark.parametrize("model", ALL_LLMS)
async def test_llm_generate(nua_client: AsyncNuaClient, model):
    np = AsyncNucliaPredict()

    @make_retry_async(attempts=3, delay=10, exceptions=(AssertionError,))
    async def test_nua_generate():
        generated = await np.generate("Which is the capital of Catalonia?", model=model, nc=nua_client)
        assert "Barcelona" in generated.answer

    await test_nua_generate()
