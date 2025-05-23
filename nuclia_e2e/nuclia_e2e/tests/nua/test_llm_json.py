from nuclia.lib.nua import AsyncNuaClient
from nuclia.lib.nua_responses import ChatModel
from nuclia.lib.nua_responses import UserPrompt
from nuclia.sdk.predict import AsyncNucliaPredict
from nuclia_e2e.models import LLM_WITH_JSON_OUTPUT_SUPPORT

import pytest

SCHEMA = {
    "name": "ClassificationReverse",
    "description": "Correctly extracted with all the required parameters with correct types",
    "parameters": {
        "properties": {
            "title": {"default": "label", "title": "Title", "type": "string"},
            "description": {
                "default": "Define labels to classify the subject of the document",
                "title": "Description",
                "type": "string",
            },
            "document_type": {
                "description": "Type of document, SPORT example: elections, Illa, POLITICAL example: football",  # noqa: E501
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
@pytest.mark.parametrize("model_name", LLM_WITH_JSON_OUTPUT_SUPPORT)
async def test_llm_json(nua_client: AsyncNuaClient, model_name):
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
    assert "SPORTS" in results.object["document_type"]
