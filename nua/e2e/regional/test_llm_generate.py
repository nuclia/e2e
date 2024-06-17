from nuclia.sdk.predict import NucliaPredict, AsyncNucliaPredict
from nuclia.lib.nua_responses import ChatModel, UserPrompt
import json
import pytest

def test_llm_generate_chatgpt(nua_config):
    np = NucliaPredict()
    generated = np.generate(
        "Which is the capital of Catalonia?", model="chatgpt-azure-3"
    )
    assert "Barcelona" in generated.answer


def test_llm_generate_azure_chatgpt(nua_config):
    np = NucliaPredict()
    generated = np.generate("Which is the capital of Catalonia?", model="chatgpt-azure")
    assert "Barcelona" in generated.answer


def test_llm_generate_claude(nua_config):
    np = NucliaPredict()
    generated = np.generate("Which is the capital of Catalonia?", model="claude-3")
    assert "Barcelona" in generated.answer


def test_llm_generate_gemini(nua_config):
    np = NucliaPredict()
    generated = np.generate("Which is the capital of Catalonia?", model="gemini-1-5-pro")
    assert "Barcelona" in generated.answer

SCHEMA = """
{"name": "ClassificationReverse", "description": "Correctly extracted with all the required parameters with correct types", "parameters": {"$defs": {"Options": {"enum": ["SPORTS", "POLITICAL"], "title": "Options", "type": "string"}}, "properties": {"title": {"default": "label", "title": "Title", "type": "string"}, "description": {"default": "Define labels to classify the subject of the document", "title": "Description", "type": "string"}, "document_type": {"description": "Type of document, SPORT example: elections, Illa, POLITICAL example: football", "items": {"$ref": "#/$defs/Options"}, "title": "Document Type", "type": "array"}}, "required": ["document_type"], "type": "object"}}
"""

TEXT = """"Many football players have existed. Messi is by far the greatest. Messi was born in Rosario, 24th of June 1987"""

pytest.mark.asyncio
async def text_llm_generate_azure_chatgpt_parse(nua_config):
    np = AsyncNucliaPredict()
    results = await np.generate(
        text=ChatModel(
            question="",
            retrieval=False,
            user_id="Nuclia PY CLI",
            user_prompt=UserPrompt(prompt=TEXT),
            json_schema=SCHEMA,
        )
    )
    assert "SPORTS" in json.loads(results.answer)["document_type"]