from nuclia.lib.nua_responses import ChatModel, UserPrompt
from nuclia.sdk.predict import AsyncNucliaPredict
from nuclia.lib.nua import AsyncNuaClient
from regional.models import ALL_LLMS
import pytest


@pytest.mark.asyncio_cooperative
async def test_llm_chat(nua_config: AsyncNuaClient):
    # Validate that other features such as
    # * citations
    # * custom prompts
    # * reranking (TODO once supported by the SDK)
    np = AsyncNucliaPredict()
    chat_model = ChatModel(
        question="Which is the CEO of Nuclia?",
        retrieval=False,
        user_id="Nuclia PY CLI",
        system="You are a helpful assistant, your first word is always the language you will be using in the conversation in all caps.\nExample: 'FRANÇAIS: Bonjour, madame.'",
        user_prompt=UserPrompt(
            prompt="Respond to the question using the context pieces provided, please answer in ITALIAN:\n Question: {question}\n Context: {context}"
        ),
        query_context={
            "1": "The CEO of Nuclia is Eudald Camprubí",
            "2": "Nuclia is a company that specializes in AI and NLP",
        },
        citations=True,
    )
    generated = await np.generate(
        text=chat_model,
        model=ALL_LLMS[0],
        nc=nua_config,
    )
    # Check that system + user prompt worked
    assert generated.answer.startswith("ITALIAN")
    # Check that citations are present and make sense
    assert "1" in generated.citations and "2" not in generated.citations
    # Check that the answer is correct
    assert "Eudald" in generated.answer
    # Check that we have input and output tokens
    assert generated.input_tokens > 50
    assert generated.output_tokens > 10
