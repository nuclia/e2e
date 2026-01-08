from nuclia.exceptions import RaoAPIException
from nuclia.lib.agent import AsyncAgentClient
from nuclia_e2e.tests.conftest import RegionalAPI
from nuclia_e2e.tests.conftest import ZoneConfig
from nuclia_e2e.utils import delete_test_kb
from nuclia_e2e.utils import get_kbid_from_slug
from nuclia_models.agent.interaction import AnswerOperation
from nuclia_models.agent.interaction import AragAnswer

import asyncio
import pytest


async def create_rao_with_agents(
    regional_api: RegionalAPI, regional_api_config: ZoneConfig, slug: str, account: str
) -> str:
    agent_id = (await regional_api.create_rao(account_id=account, slug=slug, mode="agent"))["id"]
    # Check it got created
    assert agent_id is not None
    assert regional_api_config.global_config is not None
    api_url = f"https://{regional_api_config.zone_slug}.{regional_api_config.global_config.base_domain}/api"
    account = regional_api_config.global_config.permanent_account_id
    kbid = regional_api_config.permanent_kb_id
    new_sa = await regional_api.create_service_account(account, kbid, "rao-e2e-nucliadb-driver")
    key = await regional_api.create_service_account_key(account, kbid, new_sa["id"])
    drivers = [
        {
            "name": "my-nucliadb-driver",
            "provider": "nucliadb",
            "config": {
                "kbid": regional_api_config.permanent_kb_id,
                "description": "General Knowledge KB",
                "key": key,
                "url": api_url,
                "manager": api_url,
                "filters": [],
            },
            "identifier": "nucliadb-driver",
        },
    ]
    preprocess = [
        {
            "module": "rephrase",
            "model": "chatgpt-azure-4o-mini",
        }
    ]
    context = [
        {
            "module": "basic_ask",
            "sources": ["nucliadb-driver"],
            "generative_model": "chatgpt-azure-4o-mini",
            "summarize_model": "chatgpt-azure-4o-mini",
            "title": "agent",
            "rephrase_model": "chatgpt-azure-4o-mini",
        }
    ]
    generation = [
        {
            "module": "summarize",
            "title": "agent",
            "model": "chatgpt-azure-4o-mini",
        }
    ]
    postprocess = [{"module": "remi", "title": "agent", "max_retries": 1}]
    # Add in separate steps to identify issues more easily
    # Wait a bit to ensure RAO is ready
    await asyncio.sleep(2)
    # Drivers
    for driver in drivers:
        await regional_api.rao(
            method="POST",
            agent_id=agent_id,
            endpoint="/drivers",
            payload=driver,
        )
    # Preprocess Agents
    for pre in preprocess:
        await regional_api.rao(
            method="POST",
            agent_id=agent_id,
            endpoint="/preprocess",
            payload=pre,
        )
    # Context Agents
    for ctx in context:
        await regional_api.rao(
            method="POST",
            agent_id=agent_id,
            endpoint="/context",
            payload=ctx,
        )
    # Generation Agents
    for gen in generation:
        await regional_api.rao(
            method="POST",
            agent_id=agent_id,
            endpoint="/generation",
            payload=gen,
        )
    # Postprocess Agents
    for post in postprocess:
        await regional_api.rao(
            method="POST",
            agent_id=agent_id,
            endpoint="/postprocess",
            payload=post,
        )
    return agent_id


@pytest.mark.asyncio_cooperative
async def test_rao_basic(regional_api: RegionalAPI, regional_api_config: ZoneConfig, global_api_config):
    """Basic test to check RAO works
    0. Delete any previous test RAO (just in case)
    1. Create a no-memory RAO
    2. Create a NucliaDB driver against persistent KB
    3. Create an agent in the preprocess, context, generation and postprocess steps
    4. Create a session and check it appears in the list of sessions
    5. Interact to ask a question and get an answer
    6. Delete the session
    """
    test_slug = "rao-e2e-test"
    # Cleanup any previous test RAO
    kbid = await get_kbid_from_slug(regional_api_config.zone_slug, test_slug)
    if kbid is not None:
        await delete_test_kb(regional_api_config, kbid=kbid, kb_slug=test_slug)
    assert regional_api_config.global_config is not None

    account = regional_api_config.global_config.permanent_account_id
    agent_id = await create_rao_with_agents(regional_api, regional_api_config, test_slug, account)

    agent_client = AsyncAgentClient(
        region=regional_api_config.zone_slug,
        agent_id=agent_id,
        account_id=account,
        user_token=regional_api_config.global_config.permanent_account_owner_pat_token,
    )
    # Sessions
    sess_id = await agent_client.new_session("rao-e2e-test-session")
    session = await agent_client.get_session(sess_id)
    assert session.title == "rao-e2e-test-session", "Session title does not match"
    # List sessions, scan all pages since the endpoint does not support sorting by creation date
    last = False
    found = False
    p = 0
    while not last:
        sessions = await agent_client.get_sessions(page_size=100, page=p)
        last = sessions.pagination.last
        p += 1
        found = any(s.id == sess_id for s in sessions.resources)
        if found:
            break
    assert found, "Created session not found in list"

    # Interact
    responses: list[AragAnswer] = []
    async for message in agent_client.interact(
        session_uuid=sess_id,
        question="What is Nuclia?",
    ):
        responses.append(message)
        assert len(responses) > 0
    assert responses[0].operation == AnswerOperation.START

    assert responses[1].operation == AnswerOperation.ANSWER
    assert responses[1].step
    assert responses[1].step.module == "rephrase"
    assert not responses[1].exception

    assert responses[2].operation == AnswerOperation.ANSWER
    assert responses[2].step
    assert responses[2].step.module == "basic_ask"
    assert not responses[2].exception

    assert responses[-3].operation == AnswerOperation.ANSWER
    assert responses[-3].step
    assert responses[-3].step.module == "remi"
    assert not responses[-3].exception

    assert responses[-2].operation == AnswerOperation.ANSWER
    assert responses[-2].answer
    assert "not enough" in responses[-2].answer.lower()  # Persistent KB won't have much data
    assert not responses[-2].exception

    assert responses[-1].operation == AnswerOperation.DONE

    # Delete session
    await agent_client.delete_session(sess_id)
    # Wait a bit for deletion to propagate
    await asyncio.sleep(1)

    with pytest.raises(RaoAPIException):
        await agent_client.get_session(sess_id)

    # Delete RAO for cleanup
    await delete_test_kb(regional_api_config, kbid=agent_id, kb_slug=test_slug)
