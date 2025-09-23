from nuclia.data import get_auth
from nuclia.sdk.kb import AsyncNucliaKB
from nuclia_e2e.tests.conftest import ZoneConfig
from nuclia_e2e.utils import get_async_kb_ndb_client
from nucliadb_models.search import AskRequest
from nucliadb_models.search import ChatOptions
from nucliadb_models.search import Reasoning
from nucliadb_models.search import RerankerName
from textwrap import dedent

import pytest


@pytest.mark.asyncio_cooperative
async def test_ask_with_reasoning(regional_api_config: ZoneConfig):
    kb_id = regional_api_config.permanent_kb_id
    zone = regional_api_config.zone_slug

    auth = get_auth()
    async_ndb = get_async_kb_ndb_client(zone=zone, kbid=kb_id, user_token=auth._config.token)
    kb = AsyncNucliaKB()

    ask_result = await kb.search.ask(
        ndb=async_ndb,
        show_consumption=True,
        query=AskRequest(
            autofilter=True,
            rephrase=True,
            reranker=RerankerName.PREDICT_RERANKER,
            features=[
                ChatOptions.KEYWORD,
                ChatOptions.SEMANTIC,
                ChatOptions.RELATIONS,
            ],
            reasoning=Reasoning(display=True, effort="high"),
            query="how to cook an omelette?",
            generative_model="chatgpt-azure-5",
            prompt=dedent(
                """
            Answer the following question based **only** on the provided context. Do **not** use any outside
            knowledge. If the context does not provide enough information to fully answer the question, reply
            with: “Not enough data to answer this.”
            Don't be too picky. please try to answer if possible, even if it requires to make a bit of a
            deduction.
            [START OF CONTEXT]
            {context}
            [END OF CONTEXT]
            Question: {question}
            # Notes
            - **Do not** mention the source of the context in any case
            """
            ),
        ),
    )
    assert "egg" in str(ask_result.answer)
    assert "omelette" in ask_result.reasoning
    assert ask_result.consumption is not None
