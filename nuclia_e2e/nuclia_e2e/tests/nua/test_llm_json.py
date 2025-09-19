from nuclia.lib.nua import AsyncNuaClient
from nuclia.lib.nua_responses import ChatModel
from nuclia.lib.nua_responses import UserPrompt
from nuclia.sdk.predict import AsyncNucliaPredict
from nuclia_e2e.models import JSON_OUTPUT_TEST_LLMS
from nuclia_e2e.models import model_zone_check
from nuclia_e2e.tests.conftest import ZoneConfig

import pytest

SCHEMA = {
    "name": "ClassificationReverse",
    "description": "Correctly extracted with all the required parameters with correct types",
    "parameters": {
        "properties": {
            "document_type": {
                "description": "Main theme of the text",
                "title": "Document Type",
                "type": "array",
                "items": {
                    "enum": ["SPORTS", "POLITICAL"],
                    "title": "Options",
                    "type": "string",
                },
            },
        },
        "required": ["document_type"],
        "type": "object",
    },
}

TEXT = (
    "Many football players have existed. Messi is by far the greatest. "
    "Messi was born in Rosario, 24th of June 1987"
)


@pytest.mark.asyncio_cooperative
@pytest.mark.parametrize("model_name", JSON_OUTPUT_TEST_LLMS)
async def test_llm_json(nua_client: AsyncNuaClient, model_name: str, regional_api_config: ZoneConfig):
    model_zone_check(model_name, regional_api_config.name)
    np = AsyncNucliaPredict()
    results = await np.generate(
        text=ChatModel(
            question="",
            retrieval=False,
            user_id="Nuclia PY CLI",
            user_prompt=UserPrompt(prompt=TEXT),
            json_schema=SCHEMA,
        ),
        model=model_name,
        nc=nua_client,
    )
    assert results.object is not None, "Model did not generate JSON output"
    assert "SPORTS" in results.object["document_type"], "Model did not classify document as SPORTS"
