from datetime import datetime
from datetime import timedelta
from nuclia.data import get_auth
from nuclia.sdk.kb import AsyncNucliaKB
from nuclia_e2e.tests.conftest import EmailUtil
from nuclia_e2e.tests.conftest import ZoneConfig
from nuclia_e2e.utils import get_async_kb_ndb_client
from nuclia_models.events.activity_logs import DownloadActivityLogsChatQuery
from nuclia_models.events.activity_logs import DownloadFormat
from nuclia_models.events.activity_logs import EventType
from nuclia_models.events.activity_logs import QueryFiltersChat

import aiohttp
import asyncio
import json
import pytest


async def fetch_ndjson_async(url: str):
    async with aiohttp.ClientSession() as session, session.get(url) as response:
        data = []
        async for line in response.content:
            data.append(json.loads(line.decode("utf-8")))

        return data


@pytest.mark.asyncio_cooperative
async def test_download_activity_log(regional_api_config: ZoneConfig, email_util: EmailUtil):
    kb_id = regional_api_config.permanent_kb_id
    zone = regional_api_config.zone_slug

    auth = get_auth()
    async_ndb = get_async_kb_ndb_client(zone=zone, kbid=kb_id, user_token=auth._config.token)

    date = datetime.now()

    # Very simple ask to ensure at least we have something in the database for this month and kb
    kb = AsyncNucliaKB()
    await kb.search.ask(ndb=async_ndb, query="omelette")

    test_email = email_util.generate_email_address()
    query = DownloadActivityLogsChatQuery(
        year_month=f"{date.year}-{str(date.month).zfill(2)}",
        show={"id"},
        filters=QueryFiltersChat(),
        email_address=test_email,
        notify_via_email=True,
    )
    kb = AsyncNucliaKB()
    request = await kb.logs.download(
        ndb=async_ndb, type=EventType.CHAT, query=query, download_format=DownloadFormat.NDJSON, wait=True
    )
    data = await fetch_ndjson_async(request.download_url)
    assert len(data) > 1
    await asyncio.sleep(5)
    last_email = await email_util.get_last_email_body(test_email)
    assert request.download_url in last_email
