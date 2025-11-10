from nuclia.lib.kb import AsyncNucliaDBClient
from nuclia.sdk.kb import AsyncNucliaKB
from nuclia.sdk.search import AskAnswer
from nuclia_e2e.utils import get_async_kb_ndb_client
from nucliadb_models.search import AskRequest
from nucliadb_models.search import ChatOptions
from nucliadb_models.search import RequestSecurity
from nucliadb_models.search import RerankerName

import pytest


@pytest.mark.asyncio_cooperative
async def test_kb_auth(request: pytest.FixtureRequest, regional_api_config, regional_api, clean_kb_sa):
    """
    Tests the different authorizations we have available to access the nucliadb namespace
    """

    def logger(msg):
        print(f"{request.node.name} ::: {msg}")

    zone = regional_api_config.zone_slug
    account = regional_api_config.global_config.permanent_account_id

    kbid = regional_api_config.permanent_kb_id

    new_sa = await regional_api.create_service_account(account, kbid, "test-e2e-kb-auth")
    new_sa_key = await regional_api.create_service_account_key(account, kbid, new_sa["id"])

    # Configures a nucliadb client defaulting to a specific kb, to be used
    # to override all the sdk endpoints that automagically creates the client
    # as this is incompatible with the cooperative tests

    async_ndb = get_async_kb_ndb_client(zone, kbid, service_account_token=new_sa_key)

    async def security_groups_test_ask(
        client: AsyncNucliaDBClient, question: str, security_groups: list[str] | None
    ) -> AskAnswer:
        kb = AsyncNucliaKB()
        return await kb.search.ask(
            ndb=client,
            query=AskRequest(
                query=question,
                reranker=RerankerName.PREDICT_RERANKER,
                rephrase=False,
                generative_model="chatgpt-azure-4o-mini",
                features=[ChatOptions.SEMANTIC],
                security=RequestSecurity(groups=security_groups) if security_groups is not None else None,
            ),
        )
    
    async def security_groups_test_resource_ask(
        client: AsyncNucliaDBClient, question: str, security_groups: list[str] | None
    ) -> AskAnswer:
        kb = AsyncNucliaKB()
        return await kb.search.ask(
            ndb=client,
            query=AskRequest(
                query=question,
                reranker=RerankerName.PREDICT_RERANKER,
                rephrase=False,
                generative_model="chatgpt-azure-4o-mini",
                features=[ChatOptions.SEMANTIC],
                security=RequestSecurity(groups=security_groups) if security_groups is not None else None,
            ),
        )

    # There are two resources describing to recipes
    #  - omelette          groups = apprentices, chefs
    #  - roasted chicken   groups = chefs
    # This setup is used to test failing to ask for roasted chicken if you are an apprentice
    # while testing different scenarios on how we provide security(or don't)

    # Regular SA key with no explicit security should answer correctly
    secured_question = "What do you need to make a roasted chicken?"
    answer = await security_groups_test_ask(async_ndb, secured_question, security_groups=None)
    assert answer.status == "success"
    from pprint import pprint
    pprint(answer)
    pprint(answer.object)

    # Temporal SA key with no explicit security, should allow the question
    # Recreating the key and client each time, as it has a 10 seconds ttl
    new_sa_temp_key = await regional_api.create_service_account_temp_key(new_sa_key, security_groups=None)
    async_ndb_sa_temp = get_async_kb_ndb_client(zone, kbid, service_account_token=new_sa_temp_key)
    answer = await security_groups_test_ask(async_ndb_sa_temp, secured_question, security_groups=None)
    assert answer.status == "success"

    # Regular SA key with explicit security on the request should fail this
    answer = await security_groups_test_ask(async_ndb, secured_question, security_groups=["apprentices"])
    assert answer.status == "no_context"

    # Temporal SA key with key security (injected via authorizer), should allow the question
    # Recreating the key and client each time, as it has a 10 seconds ttl
    new_sa_temp_key = await regional_api.create_service_account_temp_key(
        new_sa_key, security_groups=["apprentices"]
    )
    async_ndb_sa_temp = get_async_kb_ndb_client(zone, kbid, service_account_token=new_sa_temp_key)
    answer = await security_groups_test_ask(async_ndb_sa_temp, secured_question, security_groups=None)
    assert answer.status == "no_context"

    # # Temporal SA key with key security (injected via authorizer), should allow the question
    # # Recreating the key and client each time, as it has a 10 seconds ttl
    # new_sa_temp_key = await regional_api.create_service_account_temp_key(
    #     new_sa_key, security_groups=["apprentices"]
    # )
    # async_ndb_sa_temp = get_async_kb_ndb_client(zone, kbid, service_account_token=new_sa_temp_key)
    # answer = await security_groups_test_resource_ask(async_ndb_sa_temp, secured_question, security_groups=None)
    # assert answer.status == "no_context"

