from collections.abc import Callable
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from functools import wraps
from nuclia.data import get_auth
from nuclia.lib.kb import AsyncNucliaDBClient
from nuclia.sdk.kb import AsyncNucliaKB
from nuclia.sdk.kbs import AsyncNucliaKBS
from nuclia_e2e.utils import ASSETS_FILE_PATH
from nuclia_e2e.utils import get_async_kb_ndb_client
from nuclia_e2e.utils import get_kbid_from_slug
from nuclia_e2e.utils import wait_for
from nucliadb_models.metadata import ResourceProcessingStatus
from nucliadb_sdk.v2.exceptions import ClientError
from textwrap import dedent
from typing import Any

import aiohttp
import asyncio
import backoff
import pytest

Logger = Callable[[str], None]

TEST_CHOCO_QUESTION = "why are cocoa prices high?"
TEST_CHOCO_ASK_MORE = "When did they start being high?"


def build_loki_query(cluster: str, namespace: str, app: str, kbid: str, message_pattern: str) -> str:
    return (
        f'{{cluster="{cluster}", namespace="{namespace}", app="{app}"}} '
        f"| json "
        f"| context_kbid = `{kbid}` "
        f"| message =~ `{message_pattern}`"
    )


def datetime_to_ns(dt: datetime) -> int:
    return int(dt.timestamp() * 1e9)


async def query_loki(base_url: str, query: str, start_time: datetime, end_time: datetime) -> list[datetime]:
    start_ns = datetime_to_ns(start_time)
    end_ns = datetime_to_ns(end_time)

    url = f"{base_url}/loki/api/v1/query_range"
    params = {"query": query, "start": start_ns, "end": end_ns, "limit": 1000, "direction": "backward"}

    async with aiohttp.ClientSession() as session:
        for attempt in range(100):
            async with session.get(url, params=params) as resp:
                data = await resp.json()

                if data["status"] != "success":
                    raise RuntimeError(f"Loki query failed: {data}")

                results = data["data"]["result"]
                timestamps = []

                for stream in results:
                    for value in stream["values"]:
                        ts_ns = int(value[0])
                        ts = datetime.fromtimestamp(ts_ns / 1e9, tz=timezone.utc)
                        timestamps.append(ts)

                timestamps.sort()
                if len(timestamps) >= 2:
                    return timestamps[:2]

            await asyncio.sleep(1)
            print(attempt)
        err_msg = "Did not receive at least 2 results from Loki after 10 attempts."
        raise TimeoutError(err_msg)


async def run_test_kb_creation(regional_api_config, kb_slug, logger: Logger) -> str:
    kbs = AsyncNucliaKBS()
    new_kb = await kbs.add(
        zone=regional_api_config.zone_slug,
        slug=kb_slug,
        sentence_embedder="en-2024-04-24",
    )

    kbid = await get_kbid_from_slug(regional_api_config.zone_slug, kb_slug)
    assert kbid is not None
    logger(f"Created kb {new_kb['id']}")
    return kbid


@backoff.on_exception(backoff.constant, (AssertionError, ClientError), max_tries=5, interval=5)
async def run_test_find(regional_api_config, ndb: AsyncNucliaDBClient, logger: Logger):
    kb = AsyncNucliaKB()

    result = await kb.search.find(
        ndb=ndb,
        autofilter=True,
        rephrase=True,
        reranker="predict",
        features=["keyword", "semantic", "relations"],
        query=TEST_CHOCO_QUESTION,
        top_k=1,
    )
    assert result.resources
    first_resource = next(iter(result.resources.values()))
    assert first_resource.slug == "chocolatier"


@backoff.on_exception(backoff.constant, (AssertionError, ClientError), max_tries=5, interval=5)
async def run_test_ask(regional_api_config, ndb: AsyncNucliaDBClient, logger: Logger, model):
    kb = AsyncNucliaKB()

    ask_result = await kb.search.ask(
        ndb=ndb,
        autofilter=True,
        rephrase=True,
        reranker="predict",
        features=["keyword", "semantic", "relations"],
        query=TEST_CHOCO_QUESTION,
        generative_model=model,
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
    )
    assert "climate change" in ask_result.answer.decode().lower()

    ask_more_result = await kb.search.ask(
        ndb=ndb,
        autofilter=True,
        rephrase=True,
        reranker="predict",
        features=["keyword", "semantic", "relations"],
        context=[
            {"author": "USER", "text": TEST_CHOCO_QUESTION},
            {"author": "NUCLIA", "text": ask_result.answer.decode()},
        ],
        query=TEST_CHOCO_ASK_MORE,
        generative_model=model,
    )
    assert "earlier" in ask_more_result.answer.decode().lower()


async def run_test_kb_deletion(regional_api_config, kbid, kb_slug, logger):
    kbs = AsyncNucliaKBS()
    logger("deleting " + kbid)
    await kbs.delete(zone=regional_api_config.zone_slug, id=kbid)

    kbid = await get_kbid_from_slug(regional_api_config.zone_slug, kb_slug)
    assert kbid is None


class Timer:
    def __init__(self):
        self.start_time: datetime | None = None
        self.end_time: datetime | None = None

    @property
    def elapsed(self):
        delta = self.end_time - self.start_time
        return delta.total_seconds()

    def start(self, dt: datetime | None = None):
        self.start_time = dt if dt is not None else datetime.now(timezone.utc)
        return self.start_time

    def stop(self, dt: datetime | None = None):
        self.end_time = dt if dt is not None else datetime.now(timezone.utc)
        return self.end_time


@pytest.mark.asyncio_cooperative
async def test_benchmark_kb_ingestion(request: pytest.FixtureRequest, regional_api_config):
    """
    This test ferforms the minimal operations too upload a file and validate that is indexed
    with the purpose of benchmarking the ingestion process
    """
    test_start = datetime.now(timezone.utc)
    timings = {
        "upload": Timer(),
        "process_delay": Timer(),
        "process": Timer(),
        "index_delay": Timer(),
        "index": Timer(),
    }

    def logger(msg):
        print(f"{request.node.name} ::: {msg}")

    zone = regional_api_config.zone_slug
    auth = get_auth()
    kb_slug = f"{regional_api_config.test_kb_slug}-benchmark"

    # Make sure the kb used for this test is deleted, as the slug is reused:
    old_kbid = await get_kbid_from_slug(regional_api_config.zone_slug, kb_slug)
    if old_kbid is not None:
        await AsyncNucliaKBS().delete(zone=regional_api_config.zone_slug, id=old_kbid)

    # Creates a brand new kb that will be used troughout this test
    kbid = await run_test_kb_creation(regional_api_config, kb_slug, logger)

    # Configures a nucliadb client defaulting to a specific kb, to be used
    # to override all the sdk endpoints that automagically creates the client
    # as this is incompatible with the cooperative tests

    async_ndb = get_async_kb_ndb_client(zone, kbid, user_token=auth._config.token)

    # Upload a new resource and validate that is correctly processed and stored in nuclia
    # Also check that its index are available, by checking the amount of extracted paragraphs
    kb = AsyncNucliaKB()
    timings["upload"].start()
    await kb.upload.file(path=f"{ASSETS_FILE_PATH}/chocolatier.html", field="file", ndb=async_ndb)
    timings["upload"].stop()
    timings["process_delay"].start(timings["upload"].stop())

    # Wait for resource to be processed
    def first_resource_is_processed():
        @wraps(first_resource_is_processed)
        async def condition() -> tuple[bool, Any]:
            resources = await kb.list(ndb=async_ndb)
            if len(resources.resources) > 0:
                if resources.resources[0].metadata.status == ResourceProcessingStatus.PROCESSED:
                    resource = await kb.resource.get(
                        rid=resources.resources[0].id, ndb=async_ndb, show=["basic", "extracted"]
                    )
                    return (True, resource)
            return False, None

        return condition

    success, resource = await wait_for(first_resource_is_processed(), max_wait=180, interval=1, logger=logger)
    assert success, "File was not processed in time, PROCESSED status not found in resource"

    # Read timings of processing steps, provided by the processor and stored in extracted metadata
    # last_understanding is the timestamp of the last thing done just before sending the BrokerMessage to NDB
    processing_started = resource.data.files["file"].extracted.metadata.metadata.last_processing_start
    processing_finished = resource.data.files["file"].extracted.metadata.metadata.last_understanding

    timings["process"].start(processing_started)
    timings["process"].stop(processing_finished)
    timings["index_delay"].start(processing_finished)

    # Get timestamps from loki
    base_url = "https://loki.gcp-internal-1.nuclia.cloud"

    query = build_loki_query(
        cluster="gke-prod-1",
        namespace="nucliadb",
        app="writer",
        kbid=kbid,
        message_pattern="Pushed message to proxy.*",
    )
    timestamps = await query_loki(base_url, query, test_start, test_start + timedelta(minutes=10))
    loki_push_to_proxy = timestamps[1]

    query = build_loki_query(
        cluster="gke-prod-1",
        namespace="nucliadb",
        app="ingest-processed-consumer",
        kbid=kbid,
        message_pattern="Message processing.*",
    )
    timestamps = await query_loki(base_url, query, test_start, test_start + timedelta(minutes=10))
    loki_received_processing_bm = timestamps[1]

    timings["process_delay"].start(loki_push_to_proxy)
    timings["index_delay"].stop(loki_received_processing_bm)
    timings["index"].start(loki_received_processing_bm)

    # Wait for resource to be indexed by searching for a resource based on a content that just
    # the paragraph we're looking for contains, if that responds means the new indexed data is ready
    def resource_is_indexed(rid):
        @wraps(resource_is_indexed)
        async def condition() -> tuple[bool, Any]:
            result = await kb.search.find(
                ndb=async_ndb, features=["keyword"], reranker="noop", query="Michiko"
            )
            return len(result.resources) > 0, None

        return condition

    success, _ = await wait_for(resource_is_indexed(resource.id), logger=logger, max_wait=120, interval=0.1)
    assert success, "File was not indexed in time, not enough paragraphs found on resource"
    timings["index"].stop()

    for timer_name, timer in timings.items():
        print(f"{timer_name} elapsed: {timer.elapsed}")

    # Delete the kb as a final step
    await run_test_kb_deletion(regional_api_config, kbid, kb_slug, logger)
