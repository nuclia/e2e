from collections.abc import Coroutine
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from functools import partial
from functools import wraps
from nuclia.data import get_auth
from nuclia.lib.kb import AsyncNucliaDBClient
from nuclia.lib.kb import Environment
from nuclia.lib.kb import NucliaDBClient
from nuclia.sdk.kb import AsyncNucliaKB
from nuclia.sdk.kb import NucliaKB
from nuclia.sdk.kbs import NucliaKBS
from nuclia_models.events.activity_logs import ActivityLogsChatQuery
from nuclia_models.events.activity_logs import ActivityLogsSearchQuery
from nuclia_models.events.activity_logs import EventType
from nuclia_models.worker.proto import ApplyTo
from nuclia_models.worker.proto import Filter
from nuclia_models.worker.proto import Label
from nuclia_models.worker.proto import LabelOperation
from nuclia_models.worker.proto import LLMConfig
from nuclia_models.worker.proto import Operation
from nuclia_models.worker.tasks import ApplyOptions
from nuclia_models.worker.tasks import DataAugmentation
from nuclia_models.worker.tasks import TaskName
from nucliadb_models.metadata import ResourceProcessingStatus
from nucliadb_sdk.v2.exceptions import NotFoundError
from pathlib import Path
from textwrap import dedent
from time import monotonic
from typing import Any

import asyncio
import backoff
import pytest

NUCLIADB_KB_ENDPOINT = "/api/v1/kb/{kb}"
ASSETS_FILE_PATH = f"{Path(__file__).parent.parent}/assets"


async def wait_for(
    condition: Coroutine, max_wait: int = 60, interval: int = 1, logger=None
) -> tuple[bool, Any]:
    func_name = condition.__name__
    logger(f"start wait_for '{func_name}', max_wait={max_wait}s")
    start = monotonic()
    success, data = await condition()
    while not success and monotonic() - start < max_wait:
        await asyncio.sleep(interval)
        success, data = await condition()
    logger(f"wait_for '{func_name}' success={success} in {monotonic()-start} seconds")
    return success, data


async def get_kbid_from_slug(zone: str, slug: str) -> str:
    kbs = NucliaKBS()
    all_kbs = await asyncio.to_thread(partial(kbs.list, zone=zone))
    kbids_by_slug = {kb.slug: kb.id for kb in all_kbs}
    kbid = kbids_by_slug.get(slug)
    return kbid


def get_async_kb_ndb_client(zone, account, kbid, user_token):
    from nuclia import REGIONAL

    kb_path = NUCLIADB_KB_ENDPOINT.format(zone=zone, account=account, kb=kbid)
    base_url = REGIONAL.format(region=zone)
    kb_base_url = f"{base_url}{kb_path}"

    ndb = AsyncNucliaDBClient(
        environment=Environment.CLOUD,
        url=kb_base_url,
        user_token=user_token,
        region=zone,
    )
    return ndb


def get_sync_kb_ndb_client(zone, account, kbid, user_token):
    from nuclia import REGIONAL

    kb_path = NUCLIADB_KB_ENDPOINT.format(zone=zone, account=account, kb=kbid)
    base_url = REGIONAL.format(region=zone)
    kb_base_url = f"{base_url}{kb_path}"

    ndb = NucliaDBClient(
        environment=Environment.CLOUD,
        url=kb_base_url,
        user_token=user_token,
        region=zone,
    )
    return ndb


async def run_test_kb_creation(regional_api_config, logger) -> str:
    kbs = NucliaKBS()
    new_kb = await asyncio.to_thread(
        partial(
            kbs.add,
            zone=regional_api_config["zone_slug"],
            slug=regional_api_config["test_kb_slug"],
            sentence_embedder="en-2024-04-24",
        )
    )

    kbid = await get_kbid_from_slug(regional_api_config["zone_slug"], regional_api_config["test_kb_slug"])
    assert kbid is not None
    logger(f"Created kb {new_kb['id']}")
    return kbid


async def run_test_upload_and_process(regional_api_config, ndb, logger):
    kb = AsyncNucliaKB()
    rid = await kb.resource.create(
        title="How this chocolatier is navigating an unexpected spike in cocoa prices",
        slug="chocolatier",
        ndb=ndb,
    )
    await kb.upload.file(rid=rid, path=f"{ASSETS_FILE_PATH}/chocolatier.html", field="file", ndb=ndb)

    # Wait for resource to be processed
    def resource_is_processed(rid):
        @wraps(resource_is_processed)
        async def condition() -> tuple[bool, Any]:
            resource = await kb.resource.get(rid=rid, ndb=ndb)
            return (
                resource.metadata.status == ResourceProcessingStatus.PROCESSED,
                None,
            )

        return condition

    success, _ = (
        await wait_for(resource_is_processed(rid), logger=logger),
        "File was not processed in time",
    )
    assert success


async def run_test_import_kb(regional_api_config, ndb, logger):
    """
    Imports a kb with three resources and some labelsets already created
    """
    kb = AsyncNucliaKB()
    await kb.imports.start(path=f"{ASSETS_FILE_PATH}/e2e.financial.mini.export", ndb=ndb)

    def resources_are_imported(resources):
        @wraps(resources_are_imported)
        async def condition() -> tuple[bool, Any]:
            for slug in resources:
                try:
                    await kb.resource.get(slug=slug, ndb=ndb)
                except NotFoundError:
                    return (False, None)
            return (True, None)

        return condition

    success, _ = (
        await wait_for(resources_are_imported(["disney", "hp", "vaccines"]), max_wait=120, logger=logger),
        "Expected imported resources not found",
    )
    assert success


async def run_test_create_da_labeller(regional_api_config, ndb, logger):
    """
    Creates a config to run on all current resources and on all future ones
    """
    kb = NucliaKB()
    await asyncio.to_thread(
        partial(
            kb.task.start,
            ndb=ndb,
            task_name=TaskName.LABELER,
            apply=ApplyOptions.ALL,
            parameters=DataAugmentation(
                name="test-labels",
                on=ApplyTo.FIELD,
                filter=Filter(),
                operations=[
                    Operation(
                        label=LabelOperation(
                            labels=[
                                Label(
                                    label="TECH",
                                    description="Related to financial news in the TECH/IT industry",
                                ),
                                Label(
                                    label="HEALTH",
                                    description="Related to financial news in the HEALTHCARE industry",
                                ),
                                Label(
                                    label="FOOD",
                                    description="Related to financial news in the FOOD industry",
                                ),
                                Label(
                                    label="MEDIA",
                                    description="Related to financial news in the MEDIA industry",
                                ),
                            ],
                            ident="topic",
                            description="Topic of the article in the financial context",
                        )
                    )
                ],
                llm=LLMConfig(model="chatgpt-azure-4o-mini"),
            ),
        )
    )


async def run_test_check_da_labeller_output(regional_api_config, ndb, logger):
    kb = NucliaKB()

    expected_resource_labels = [
        ("disney", ("topic", "MEDIA")),
        ("hp", ("topic", "TECH")),
        ("chocolatier", ("topic", "FOOD")),
        ("vaccines", ("topic", "HEALTH")),
    ]

    def resources_are_labelled(expected):
        @wraps(resources_are_labelled)
        async def condition() -> tuple[bool, Any]:
            result = False
            for resource_slug, (labelset, label) in expected:
                try:
                    res = await asyncio.to_thread(
                        partial(kb.resource.get, slug=resource_slug, show=["extracted"], ndb=ndb)
                    )
                except NotFoundError:
                    # some resource may still be missing from nucliadb, let's wait more
                    continue
                for fc in res.computedmetadata.field_classifications:
                    if fc.field.field_type.name == "GENERIC":
                        # in case only generic fields are found,
                        # result won't be ever true and condition will fail.
                        continue

                    # heuristic, but si@pytest.mark.asynciomple enough for now,
                    # field type async defines field name
                    field_name = fc.field.field_type.name.lower()
                    field_group_name = f"{field_name}s"
                    extracted_labels = tuple(
                        cl.label
                        for cl in res.data.__dict__[field_group_name][
                            field_name
                        ].extracted.metadata.metadata.classifications
                    )
                    computed_labels = tuple(cl.label for cl in fc.classifications)

                    if label in computed_labels[0]:
                        result = True
                    if label in extracted_labels:
                        result = True
                    if result is False:
                        # Don't check the rest if one is wrong
                        return (False, None)
            return (result, None)

        return condition

    success, _ = (
        await wait_for(resources_are_labelled(expected_resource_labels), logger=logger),
        "Expected computed labels not found in resources",
    )
    assert success


async def run_test_find(regional_api_config, ndb, logger):
    kb = AsyncNucliaKB()

    result = await kb.search.find(
        ndb=ndb,
        autofilter=True,
        rephrase=True,
        reranker="predict",
        features=["keyword", "semantic", "relations"],
        query="why cocoa prices high?",
    )
    assert result.resources
    first_resource = next(iter(result.resources.values()))
    assert first_resource.slug == "chocolatier"


@backoff.on_exception(backoff.constant, AssertionError, max_tries=15, interval=1)
async def run_test_ask(regional_api_config, ndb, logger):
    kb = AsyncNucliaKB()

    ask_result = await kb.search.ask(
        ndb=ndb,
        autofilter=True,
        rephrase=True,
        reranker="predict",
        features=["keyword", "semantic", "relations"],
        query="why cocoa prices high?",
        model="chatgpt4o",
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
            {"author": "USER", "text": "why cocoa prices high?"},
            {"author": "NUCLIA", "text": ask_result.answer.decode()},
        ],
        query="Since when are high?",
        model="chatgpt4o",
    )
    assert "earlier" in ask_more_result.answer.decode().lower()


async def run_test_activity_log(regional_api_config, ndb, logger):
    kb = NucliaKB()
    now = datetime.now(tz=timezone.utc)

    def activity_log_is_stored():
        @wraps(activity_log_is_stored)
        async def condition() -> tuple[bool, Any]:
            logs = await asyncio.to_thread(
                partial(
                    kb.logs.query,
                    ndb=ndb,
                    type=EventType.CHAT,
                    query=ActivityLogsChatQuery(year_month=f"{now.year}-{now.month:02}", filters={}),
                )
            )
            if len(logs.data) >= 2:
                # as the asks may be retried more than once (because some times rephrase doesn't always work)
                # we need to check the last logs. The way the tests are setup if we reach here is because we
                # validated that we got the expected results on ask, so the log should match this reasoning.
                if (
                    logs.data[-2].question == "why cocoa prices high?"
                    and logs.data[-1].question == "Since when are high?"
                ):
                    return (True, logs)
            return (False, None)

        return condition

    success, logs = await wait_for(activity_log_is_stored(), max_wait=90, logger=logger)
    assert success, "Activity logs didn't get stored in time"

    # if we have the ask events, we'll must have the find ones, as they have been done earlier.
    logs = await asyncio.to_thread(
        partial(
            kb.logs.query,
            ndb=ndb,
            type=EventType.SEARCH,
            query=ActivityLogsSearchQuery(year_month=f"{now.year}-{now.month:02}", filters={}),
        )
    )
    assert logs.data[-1].question == "why cocoa prices high?"


async def run_test_remi_query(regional_api_config, ndb, logger):
    kb = NucliaKB()
    starting_at = datetime.now(tz=timezone.utc) - timedelta(
        seconds=600
    )  # 10 minutes is longer than we need, indicating a "safe start" indicator for this test run
    to = starting_at + timedelta(hours=1)

    def remi_data_is_computed():
        @wraps(remi_data_is_computed)
        async def condition() -> tuple[bool, Any]:
            scores = await asyncio.to_thread(
                partial(
                    kb.remi.get_scores,
                    ndb=ndb,
                    starting_at=starting_at,
                    to=to,
                    aggregation="day",
                )
            )
            if len(scores[0].metrics) > 0:
                return (True, scores)
            return (False, None)

        return condition

    _, success = await wait_for(remi_data_is_computed(), max_wait=120, logger=logger)
    assert success, "Remi scores didn't get computed in time"


async def run_test_kb_deletion(regional_api_config, kbid, logger):
    kbs = NucliaKBS()
    logger("deleting " + kbid)
    await asyncio.to_thread(partial(kbs.delete, zone=regional_api_config["zone_slug"], id=kbid))

    kbid = await get_kbid_from_slug(regional_api_config["zone_slug"], regional_api_config["test_kb_slug"])
    assert kbid is None


@pytest.mark.asyncio_cooperative
async def test_kb(request, regional_api_config, clean_kb_test):
    """
    Test a chain of operations that simulates a normal use of a knowledgebox, just concentrated
    in time.

    These tests are not individual tests in order to be able to test stuff with newly created
    knowledgebox, without creating a lot of individual kb's for more atomic tests, just to avoid
    wasting our resources. The value of doing that on a new kb each time, is being able to catch
    any error that may not be catches by using a preexisting kb with older parameters.

    A part of this tests is sequential, as it is important to guarantee the state before moving on
    while other parts can be run concurrently, hence the use of `gather` in some points
    """

    def logger(msg):
        print(f"{request.node.name} ::: {msg}")

    print()
    logger("starting test")

    zone = regional_api_config["zone_slug"]
    account = regional_api_config["permanent_account_id"]
    auth = get_auth()

    # Creates a brand new kb that will be used troughout this test
    kbid = await run_test_kb_creation(regional_api_config, logger)

    # Configures a nucliadb client defaulting to a specific kb, to be used
    # to override all the sdk endpoints that automagically creates the client
    # as this is incompatible with the cooperative tests
    async_ndb = get_async_kb_ndb_client(zone, account, kbid, auth._config.token)
    sync_ndb = get_sync_kb_ndb_client(zone, account, kbid, auth._config.token, sync=True)

    # Import a preexisting export containing several resources (coming from the financial-news kb)
    # and wait for the resources to be completely imported
    await run_test_import_kb(regional_api_config, async_ndb, logger)

    # Create a labeller configuration, with the goal of testing two tings:
    # - labelling of existing resources (the ones imported)
    # - labelling of new resources(will be created later)
    await run_test_create_da_labeller(regional_api_config, sync_ndb, logger)

    # Upload a new resource and validate that is correctly processed and stored in nuclia
    await run_test_upload_and_process(regional_api_config, async_ndb, logger)

    # Wait for both labeller task results to be consolidated in nucliadb while we also run semantic search
    # This /find and /ask requests are crafted so they trigger all the existing calls to predict features
    # We wait until find succeeds to run the ask tests to maximize the changes that all indexes will be
    # available and so minimize the llm costs retrying
    await asyncio.gather(
        run_test_check_da_labeller_output(regional_api_config, sync_ndb, logger),
        run_test_find(regional_api_config, async_ndb, logger),
    )
    await run_test_ask(regional_api_config, async_ndb, logger)

    # Validate that all the data about the usage we generated is correctly stored on the activity log
    # and can be queried, and that the remi quality metrics. Even if the remi metrics won't be computed until
    # the activity log is stored, the test_activity_log tests several things aside the ask events (the ones
    # affecting the remi queries) and so we can benefit of running them in parallel.
    await asyncio.gather(
        run_test_activity_log(regional_api_config, sync_ndb, logger),
        run_test_remi_query(regional_api_config, sync_ndb, logger),
    )

    # Delete the kb as a final step
    await run_test_kb_deletion(regional_api_config, kbid, logger)