from datetime import datetime
from nuclia.data import get_auth
from nuclia.sdk.kb import AsyncNucliaKB
from nuclia_e2e.tests.conftest import EmailUtil
from nuclia_e2e.tests.conftest import ZoneConfig
from nuclia_e2e.utils import get_async_kb_ndb_client
from nuclia_e2e.utils import wait_for
from nuclia_models.common.pagination import Pagination
from nuclia_models.events.activity_logs import ActivityLogsAskQuery
from nuclia_models.events.activity_logs import DownloadActivityLogsAskQuery
from nuclia_models.events.activity_logs import DownloadFormat
from nuclia_models.events.activity_logs import EventType
from nuclia_models.events.activity_logs import QueryFiltersAsk
from nuclia_models.events.activity_logs import StringFilter
from urllib.parse import unquote_plus
from urllib.parse import urlparse
from urllib.parse import urlunparse

import aiohttp
import asyncio
import json
import pytest
import re
import uuid


def strip_query_params(url):
    return urlunparse(urlparse(url)._replace(query=""))


async def fetch_ndjson_async(url: str):
    async with aiohttp.ClientSession() as session, session.get(url) as response:
        data = []
        async for line in response.content:
            data.append(json.loads(line.decode("utf-8")))

        return data


def extract_download_url_from_email(email_html: str) -> str:
    """Extract the download URL from the button with class 'button-a button-a-primary' in the email HTML."""
    # Pattern to match the href attribute of the button with the specific classes
    pattern = r'<a[^>]*class="[^"]*button-a button-a-primary[^"]*"[^>]*href="([^"]*)"'
    match = re.search(pattern, email_html)
    if match:
        return match.group(1)
    msg = "Could not find download URL in email HTML"
    raise ValueError(msg)


async def wait_for_download_url(kb, async_ndb, request, email_util: EmailUtil, test_email: str):
    status_download_url = request.download_url
    email_download_url = None

    for _ in range(72):  # up to ~6 extra minutes
        if status_download_url is None:
            request = await kb.logs.download_status(ndb=async_ndb, request_id=request.request_id)
            status_download_url = request.download_url

        email_body = await email_util.get_last_email_body(test_email)
        if email_body:
            email_download_url = extract_download_url_from_email(email_body)

        if status_download_url is not None or email_download_url is not None:
            return status_download_url, email_download_url

        await asyncio.sleep(5)

    return status_download_url, email_download_url


async def wait_for_ask_activity_log(kb, async_ndb, year_month: str, question: str):
    def ask_activity_log_is_stored():
        async def condition():
            logs = await kb.logs.query(
                ndb=async_ndb,
                type=EventType.ASK,
                query=ActivityLogsAskQuery(
                    year_month=year_month,
                    filters=QueryFiltersAsk(question=StringFilter(eq=question)),  # type: ignore[call-arg]
                    pagination=Pagination(limit=10),
                ),
            )
            return (any(log.question == question for log in logs.data), logs)

        return condition

    return await wait_for(ask_activity_log_is_stored(), max_wait=180, interval=5)


@pytest.mark.asyncio_cooperative
async def test_download_activity_log(regional_api_config: ZoneConfig, email_util: EmailUtil, kb_id: str):
    zone = regional_api_config.zone_slug

    auth = get_auth()
    async_ndb = get_async_kb_ndb_client(zone=zone, kbid=kb_id, user_token=auth._config.token)

    date = datetime.now()

    # Very simple ask to ensure at least we have something in the database for this month and kb
    kb = AsyncNucliaKB()
    activity_log_query = f"omelette activity log export {uuid.uuid4().hex}"
    await kb.search.ask(ndb=async_ndb, query=activity_log_query)

    year_month = f"{date.year}-{str(date.month).zfill(2)}"
    success, _ = await wait_for_ask_activity_log(kb, async_ndb, year_month, activity_log_query)
    assert success, "Ask activity log was not generated in time"

    test_email = email_util.generate_email_address()
    query = DownloadActivityLogsAskQuery(
        year_month=year_month,
        show={"id"},
        filters=QueryFiltersAsk(question=StringFilter(eq=activity_log_query)),  # type: ignore[call-arg]
        email_address=test_email,
        notify_via_email=True,
    )
    kb = AsyncNucliaKB()
    request = await kb.logs.download(
        ndb=async_ndb, type=EventType.ASK, query=query, download_format=DownloadFormat.NDJSON, wait=True
    )
    status_download_url, email_download_url = await wait_for_download_url(
        kb, async_ndb, request, email_util, test_email
    )
    download_url = status_download_url or email_download_url
    assert download_url is not None, "Download URL was not generated in time"
    data = await fetch_ndjson_async(download_url)
    assert len(data) > 1
    if email_download_url is None:
        for _ in range(12):  # up to ~1 extra minute
            await asyncio.sleep(5)
            last_email = await email_util.get_last_email_body(test_email)
            if last_email:
                email_download_url = extract_download_url_from_email(last_email)
                break
    assert email_download_url is not None, "Download email was not generated in time"

    async with (
        aiohttp.ClientSession() as session,
        session.head(email_download_url, allow_redirects=True) as resp,
    ):
        redirected_url = str(resp.url)
    if status_download_url is not None:
        assert strip_query_params(status_download_url) == strip_query_params(unquote_plus(redirected_url))
