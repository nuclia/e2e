from datetime import datetime
from nuclia.data import get_auth
from nuclia.sdk.kb import AsyncNucliaKB
from nuclia_e2e.tests.conftest import EmailUtil
from nuclia_e2e.tests.conftest import ZoneConfig
from nuclia_e2e.utils import get_async_kb_ndb_client
from nuclia_e2e.utils import wait_for
from nuclia_models.common.pagination import Pagination
from nuclia_models.events.activity_logs import ActivityLogsSearchQuery
from nuclia_models.events.activity_logs import DownloadActivityLogsSearchQuery
from nuclia_models.events.activity_logs import DownloadFormat
from nuclia_models.events.activity_logs import EventType
from nuclia_models.events.activity_logs import QueryFiltersSearch
from nuclia_models.events.activity_logs import StringFilter
from urllib.parse import unquote_plus
from urllib.parse import urlparse
from urllib.parse import urlunparse

import aiohttp
import json
import pytest
import re
import uuid

DOWNLOAD_URL_MAX_WAIT = 180


def strip_query_params(url: str) -> str:
    return urlunparse(urlparse(url)._replace(query=""))


async def fetch_ndjson_async(url: str):
    async with aiohttp.ClientSession() as session, session.get(url) as response:
        data = []
        async for line in response.content:
            data.append(json.loads(line.decode("utf-8")))

        return data


def extract_download_url_from_email(email_html: str) -> str:
    pattern = r'<a[^>]*class="[^"]*button-a button-a-primary[^"]*"[^>]*href="([^"]*)"'
    match = re.search(pattern, email_html)
    if match:
        return match.group(1)
    msg = "Could not find download URL in email HTML"
    raise ValueError(msg)


async def wait_for_search_activity_log(kb, async_ndb, year_month: str, question: str):
    def search_activity_log_is_stored():
        async def condition():
            logs = await kb.logs.query(
                ndb=async_ndb,
                type=EventType.SEARCH,
                query=ActivityLogsSearchQuery(
                    year_month=year_month,
                    filters=QueryFiltersSearch(question=StringFilter(eq=question)),  # type: ignore[call-arg]
                    pagination=Pagination(limit=10),
                ),
            )
            return (any(log.question == question for log in logs.data), logs)

        return condition

    return await wait_for(search_activity_log_is_stored(), max_wait=180, interval=5)


async def wait_for_download_url(kb, async_ndb, request_id: str):
    async def download_url_is_available():
        status = await kb.logs.download_status(ndb=async_ndb, request_id=request_id)
        return (status.download_url is not None, status)

    return await wait_for(download_url_is_available, max_wait=DOWNLOAD_URL_MAX_WAIT, interval=10)


async def wait_for_email_body(email_util: EmailUtil, test_email: str):
    async def email_is_received():
        body = await email_util.get_last_email_body(test_email)
        return (body is not None, body)

    return await wait_for(email_is_received, max_wait=60, interval=5)


@pytest.mark.asyncio_cooperative
async def test_download_activity_log(regional_api_config: ZoneConfig, kb_id: str, email_util: EmailUtil):
    zone = regional_api_config.zone_slug

    auth = get_auth()
    async_ndb = get_async_kb_ndb_client(zone=zone, kbid=kb_id, user_token=auth._config.token)

    date = datetime.now()

    # Generate one fresh search event for this month and KB without depending on generative providers.
    kb = AsyncNucliaKB()
    activity_log_query = f"omelette activity log export {uuid.uuid4().hex}"
    await kb.search.find(ndb=async_ndb, query=activity_log_query, features=["keyword"], rephrase=False)

    year_month = f"{date.year}-{str(date.month).zfill(2)}"
    success, _ = await wait_for_search_activity_log(kb, async_ndb, year_month, activity_log_query)
    assert success, "Search activity log was not generated in time"

    test_email = email_util.generate_email_address()
    query = DownloadActivityLogsSearchQuery(
        year_month=year_month,
        show={"id"},
        filters=QueryFiltersSearch(question=StringFilter(eq=activity_log_query)),  # type: ignore[call-arg]
        email_address=test_email,
        notify_via_email=True,
    )
    request = await kb.logs.download(
        ndb=async_ndb, type=EventType.SEARCH, query=query, download_format=DownloadFormat.NDJSON, wait=True
    )
    assert request.request_id
    assert request.kb_id == kb_id
    assert request.event_type == EventType.SEARCH
    assert request.download_format == DownloadFormat.NDJSON

    success, status = await wait_for_download_url(kb, async_ndb, request.request_id)
    assert success, f"Activity log download URL was not generated in time. Last status: {status!r}"
    assert status.request_id == request.request_id
    assert status.kb_id == kb_id
    assert status.event_type == EventType.SEARCH
    assert status.download_format == DownloadFormat.NDJSON
    assert status.download_url is not None

    download_url = status.download_url
    data = await fetch_ndjson_async(download_url)
    assert len(data) >= 1

    success, last_email = await wait_for_email_body(email_util, test_email)
    assert success, f"Activity log download email was not received at {test_email}"
    assert last_email is not None

    email_download_url = extract_download_url_from_email(last_email)
    async with (
        aiohttp.ClientSession() as session,
        session.head(email_download_url, allow_redirects=True) as resp,
    ):
        redirected_url = str(resp.url)
    assert strip_query_params(download_url) == strip_query_params(unquote_plus(redirected_url))
