import pytest
from nuclia.lib.nua_responses import ChatModel, UserPrompt
from nuclia.sdk.predict import NucliaPredict

LLM_WITH_JSON_OUTPUT_SUPPORT = [
    "chatgpt-azure-4-turbo",
    "chatgpt-azure-4o",
    "claude-3",
    "claude-3-fast",
    "claude-3-5-fast",
    "chatgpt4",
    "chatgpt4o",
    "chatgpt4o-mini",
    "gemini-1-5-pro",
    "azure-mistral",
]
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
                "description": "Type of document, SPORT example: elections, Illa, POLITICAL example: football",
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

TEXT = """"Many football players have existed. Messi is by far the greatest. Messi was born in Rosario, 24th of June 1987"""


@pytest.mark.parametrize("model_name", LLM_WITH_JSON_OUTPUT_SUPPORT)
def test_llm_json(nua_config, model_name):
    np = NucliaPredict()
    results = np.generate(
        text=ChatModel(
            question="",
            retrieval=False,
            user_id="Nuclia PY CLI",
            user_prompt=UserPrompt(prompt=TEXT),
            json_schema=SCHEMA,
        ),
        model=model_name,
    )
    assert "SPORTS" in results.object["document_type"]
