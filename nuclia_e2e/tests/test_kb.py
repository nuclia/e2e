from datetime import datetime
from datetime import timedelta
from datetime import timezone
from functools import partial
from functools import wraps
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
from time import monotonic
from typing import Any
from typing import Coroutine

import asyncio
import backoff
import pytest

ASSETS_FILE_PATH = f"{Path(__file__).parent.parent}/assets"


async def wait_for(condition: Coroutine, max_wait: int = 60, interval: int = 1) -> tuple[bool, Any]:
    func_name = condition.__name__
    print(f"start wait_for '{func_name}', max_wait={max_wait}s")
    start = monotonic()
    success, data = await condition()
    while not success and monotonic() - start < max_wait:
        await asyncio.sleep(interval)
        success, data = await condition()
    print(f"wait_for '{func_name}' success={success} in {monotonic()-start} seconds")
    return success, data


async def get_kbid_from_slug(slug: str) -> str:
    kbs = NucliaKBS()
    all_kbs = await asyncio.to_thread(kbs.list)
    kbids_by_slug = {kb.slug: kb.id for kb in all_kbs}
    kbid = kbids_by_slug.get(slug)
    return kbid


async def run_test_kb_creation(regional_api_config):
    kbs = NucliaKBS()
    new_kb = await asyncio.to_thread(
        partial(
            kbs.add,
            slug=regional_api_config["test_kb_slug"],
            sentence_embedder="en-2024-04-24",
        )
    )

    kbid = await get_kbid_from_slug(regional_api_config["test_kb_slug"])
    assert kbid is not None
    kbs.default(kbid)
    print(f"Created kb {new_kb['id']}")


async def run_test_upload_and_process(regional_api_config):
    kb = AsyncNucliaKB()
    rid = await kb.resource.create(
        title="How this chocolatier is navigating an unexpected spike in cocoa prices",
        slug="chocolatier",
    )
    await kb.upload.file(rid=rid, path=f"{ASSETS_FILE_PATH}/chocolatier.html", field="file")

    # Wait for resource to be processed
    def resource_is_processed(rid):
        @wraps(resource_is_processed)
        async def condition() -> tuple[bool, Any]:
            resource = await kb.resource.get(rid=rid)
            return (
                resource.metadata.status == ResourceProcessingStatus.PROCESSED,
                None,
            )

        return condition

    success, _ = (
        await wait_for(resource_is_processed(rid)),
        "File was not processed in time",
    )
    assert success


async def run_test_import_kb(regional_api_config):
    """
    Imports a kb with three resources and some labelsets already created
    """
    kb = AsyncNucliaKB()
    await kb.imports.start(path=f"{ASSETS_FILE_PATH}/e2e.financial.mini.export")

    def resources_are_imported(resources):
        @wraps(resources_are_imported)
        async def condition() -> tuple[bool, Any]:
            for slug in resources:
                try:
                    await kb.resource.get(slug=slug)
                except NotFoundError:
                    return (False, None)
            return (True, None)

        return condition

    success, _ = (
        await wait_for(resources_are_imported(["disney", "hp", "vaccines"]), max_wait=120),
        "Expected imported resources not found",
    )
    assert success


async def run_test_create_da_labeller(regional_api_config):
    """
    Creates a config to run on all current resources and on all future ones
    """
    kb = NucliaKB()
    await asyncio.to_thread(
        partial(
            kb.task.start,
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


async def run_test_check_da_labeller_output(regional_api_config):
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
                    res = kb.resource.get(slug=resource_slug, show=["extracted"])
                except NotFoundError:
                    # some resource may still be missing from nucliadb, let's wait more
                    continue
                for fc in res.computedmetadata.field_classifications:
                    if fc.field.field_type.name == "GENERIC":
                        # in case only generic fields are found, result won't be ever trur and condition will fail.
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
        await wait_for(resources_are_labelled(expected_resource_labels)),
        "Expected computed labels not found in resources",
    )
    assert success


async def run_test_find(regional_api_config):
    kb = AsyncNucliaKB()

    result = await kb.search.find(
        autofilter=True,
        rephrase=True,
        reranker="predict",
        features=["keyword", "semantic", "relations"],
        query="why cocoa prices high?",
    )
    assert result.resources
    first_resource = next(iter(result.resources.values()))
    assert first_resource.slug == "chocolatier"


@backoff.on_exception(backoff.constant, AssertionError, max_tries=15, interval=0)
async def run_test_ask(regional_api_config):
    kb = AsyncNucliaKB()

    ask_result = await kb.search.ask(
        autofilter=True,
        rephrase=True,
        reranker="predict",
        features=["keyword", "semantic", "relations"],
        query="why cocoa prices high?",
        model="chatgpt4o",
    )

    assert "climate change" in ask_result.answer.decode().lower()
    ask_more_result = await kb.search.ask(
        autofilter=True,
        rephrase=True,
        reranker="predict",
        features=["keyword", "semantic", "relations"],
        context=[
            {"author": "USER", "text": "why cocoa prices high?"},
            {"author": "NUCLIA", "text": ask_result.answer.decode()},
        ],
        query="when?",
        model="chatgpt4o",
    )
    assert "earlier" in ask_more_result.answer.decode().lower()


async def run_test_remi_query(regional_api_config):
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
                    starting_at=starting_at,
                    to=to,
                    aggregation="day",
                )
            )
            if len(scores[0].metrics) > 0:
                return (True, scores)
            return (False, None)

        return condition

    success, _ = (
        await wait_for(
            remi_data_is_computed(),
            max_wait=2400,
        ),
    )
    assert success, "Remi scores didn't get computed in time"


async def run_test_activity_log(regional_api_config):
    kb = NucliaKB()
    now = datetime.now(tz=timezone.utc)

    def activity_log_is_stored():
        @wraps(activity_log_is_stored)
        async def condition() -> tuple[bool, Any]:
            logs = await asyncio.to_thread(
                partial(
                    kb.logs.query,
                    type=EventType.CHAT,
                    query=ActivityLogsChatQuery(year_month="{dt.year}-{dt.month}".format(dt=now), filters={}),
                )
            )
            if len(logs.data) >= 2:
                # as the asks may be retried more than once (because some times rephrase doesn't always work)
                # we need to check the last logs. The way the tests are setup if we reach here is because we validated
                # that we got the expected results on ask, so the log should match this reasoning.
                if logs.data[-2].question == "why cocoa prices high?" and logs.data[-1].question == "when?":
                    return (True, logs)
            return (False, None)

        return condition

    success, logs = await wait_for(activity_log_is_stored(), max_wait=120)
    assert success, "Activity logs didn't get stored in time"

    # if we have the ask events, we'll must have the find ones, as they have been done earlier.
    logs = await asyncio.to_thread(
        partial(
            kb.logs.query,
            type=EventType.SEARCH,
            query=ActivityLogsSearchQuery(year_month="{dt.year}-{dt.month}".format(dt=now), filters={}),
        )
    )
    assert logs.data[-1].question == "why cocoa prices high?"


async def run_test_kb_deletion(regional_api_config):
    kbs = NucliaKBS()
    print("deleting " + regional_api_config["test_kb_slug"])
    await asyncio.to_thread(partial(kbs.delete, slug=regional_api_config["test_kb_slug"]))

    kbid = await get_kbid_from_slug(regional_api_config["test_kb_slug"])
    assert kbid is None


@pytest.mark.asyncio_cooperative
async def test_kb(regional_api_config, clean_kb_test):
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
    # Create a brand new kb that will be used troughout this test
    await run_test_kb_creation(regional_api_config)

    # Import a preexisting export containing several resources (coming from the financial-news kb)
    # and wait for the resources to be completely imported
    await run_test_import_kb(regional_api_config)

    # Create a labeller configuration, with the goal of testing two tings:
    # - labelling of existing resources (the ones imported)
    # - labelling of new resources(will be created later)
    await run_test_create_da_labeller(regional_api_config)

    # Upload a new resource and validate that is correctly processed and stored in nuclia
    (await run_test_upload_and_process(regional_api_config),)

    # Wait for both labeller task results to be consolidated in nucliadb while we also run  semantic search
    # and a generative question. This /find and /ask requests are crafted so they trigger all the existing calls
    # to predict features
    await asyncio.gather(
        run_test_check_da_labeller_output(regional_api_config),
        run_test_find(regional_api_config),
        run_test_ask(regional_api_config),
    )

    # Validate that all the data about the usage we generated is correctly stored on the activity log
    # and can be queried, and that the remi quality metrics. Even if the remi metrics won't be computed until
    # the activity log is stored, the test_activity_log tests several things aside the ask events (the ones
    # affecting the remi queries) and so we can benefit of running them in parallel.
    await asyncio.gather(
        run_test_activity_log(regional_api_config),
        # DISABLED until we integrate remiv2
        # run_test_remi_query(regional_api_config)
    )

    # Delete the kb as a final step
    await run_test_kb_deletion(regional_api_config)
