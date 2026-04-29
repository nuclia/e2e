from datetime import datetime
from nuclia.data import get_auth
from nuclia.sdk.kb import AsyncNucliaKB
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

import pytest
import uuid


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
async def test_download_activity_log(regional_api_config: ZoneConfig, kb_id: str):
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

    query = DownloadActivityLogsAskQuery(
        year_month=year_month,
        show={"id"},
        filters=QueryFiltersAsk(question=StringFilter(eq=activity_log_query)),  # type: ignore[call-arg]
    )
    request = await kb.logs.download(
        ndb=async_ndb, type=EventType.ASK, query=query, download_format=DownloadFormat.NDJSON
    )
    assert request.request_id
    assert request.kb_id == kb_id
    assert request.event_type == EventType.ASK
    assert request.download_format == DownloadFormat.NDJSON

    status = await kb.logs.download_status(ndb=async_ndb, request_id=request.request_id)
    assert status.request_id == request.request_id
    assert status.kb_id == kb_id
