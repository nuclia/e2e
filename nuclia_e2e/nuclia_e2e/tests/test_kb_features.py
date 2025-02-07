from collections.abc import Callable
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from functools import partial
from functools import wraps
from nuclia.data import get_auth
from nuclia.lib.kb import AsyncNucliaDBClient
from nuclia.lib.kb import NucliaDBClient
from nuclia.sdk.kb import AsyncNucliaKB
from nuclia.sdk.kb import NucliaKB
from nuclia.sdk.kbs import NucliaKBS
from nuclia_e2e.utils import ASSETS_FILE_PATH
from nuclia_e2e.utils import get_async_kb_ndb_client
from nuclia_e2e.utils import get_kbid_from_slug
from nuclia_e2e.utils import get_sync_kb_ndb_client
from nuclia_e2e.utils import wait_for
from nuclia_models.common.pagination import Pagination
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
from nuclia_models.worker.tasks import SemanticModelMigrationParams
from nuclia_models.worker.tasks import TaskName
from nucliadb_models.metadata import ResourceProcessingStatus
from nucliadb_sdk.v2.exceptions import NotFoundError
from textwrap import dedent
from typing import Any

import asyncio
import backoff
import pytest

Logger = Callable[[str], None]

TEST_CHOCO_QUESTION = "why are cocoa prices high?"
TEST_CHOCO_ASK_MORE = "When did they start being high?"


async def run_test_kb_creation(regional_api_config, logger: Logger) -> str:
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


async def run_test_upload_and_process(regional_api_config, ndb: AsyncNucliaDBClient, logger: Logger):
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
        "File was not processed in time, PROCESSED status not found in resource",
    )

    # Wait for resource to be indexed by searching for a resource based on a content that just
    # the paragraph we're looking for contains
    def resource_is_indexed(rid):
        @wraps(resource_is_indexed)
        async def condition() -> tuple[bool, Any]:
            result = await kb.search.find(ndb=ndb, features=["keyword"], query="Michiko")
            return len(result.resources) > 0, None

        return condition

    success, _ = (
        await wait_for(resource_is_indexed(rid), logger=logger, max_wait=120, interval=1),
        "File was not indexed in time, not enough paragraphs found on resource",
    )

    assert success


async def run_test_import_kb(regional_api_config, ndb: AsyncNucliaDBClient, logger: Logger):
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

    success, _ = await wait_for(
        resources_are_imported(["disney", "hp", "vaccines"]), max_wait=120, logger=logger
    )
    assert success, "Expected imported resources not found"


async def run_test_create_da_labeller(regional_api_config, ndb: NucliaDBClient, logger: Logger):
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


async def run_test_check_da_labeller_output(regional_api_config, ndb: NucliaDBClient, logger: Logger):
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


async def run_test_start_embedding_model_migration_task(
    sync_ndb: NucliaDBClient, async_ndb: AsyncNucliaDBClient
) -> str:
    assert async_ndb.kbid == sync_ndb.kbid, "why are nucliadb clients pointing to different KBs?"
    kbid = async_ndb.kbid

    # XXX: this is a really naive way to select a self-hosted model for a KB
    # without listing learning_config. At some point, we should implement
    # something smarter.
    #
    # This model names are coupled with learning_models library and a change
    # there could break this test
    vectorsets = await async_ndb.ndb.list_vector_sets(kbid=kbid)
    assert len(vectorsets.vectorsets) == 1
    current_model = vectorsets.vectorsets[0].id
    new_model = "multilingual-2024-05-06" if current_model == "en-2024-04-24" else "en-2024-04-24"

    # we first need to add the new embedding model in the KB
    created = await async_ndb.ndb.add_vector_set(kbid=kbid, vectorset_id=new_model)
    vectorset_id = created.id

    # now we can add a migration task that will reprocess all KB data with the
    # new model and store it in nucliadb
    kb = NucliaKB()
    task = await asyncio.to_thread(
        partial(
            kb.task.start,
            ndb=sync_ndb,
            task_name=TaskName.SEMANTIC_MODEL_MIGRATOR,
            apply=ApplyOptions.ALL,
            parameters=SemanticModelMigrationParams(
                semantic_model_id=vectorset_id,
            ),
        )
    )
    return task.id


async def run_test_check_embedding_model_migration(
    sync_ndb: NucliaDBClient, async_ndb: AsyncNucliaDBClient, task_id: str, logger: Logger
):
    def new_embedding_model_available() -> Callable[[], Awaitable[tuple[bool, bool | None]]]:
        @wraps(new_embedding_model_available)
        async def condition() -> tuple[bool, bool | None]:
            search_returned_results = False
            kb = NucliaKB()

            task = await asyncio.to_thread(partial(kb.task.get, ndb=sync_ndb, task_id=task_id))
            if not task.request.completed:
                # we have to wait until task has finished to try if it worked
                return (False, search_returned_results)

            new_model = task.request.parameters.semantic_model_id

            # once finished, let's try a fast /find and validate there are
            # results with the new semantic model
            result = await kb.search.find(
                ndb=async_ndb,
                rephrase=False,
                reranker="noop",
                features=["semantic"],
                vectorset=new_model,
                query=TEST_CHOCO_QUESTION,
            )
            search_returned_results = bool(result.resources)
            return (True, search_returned_results)

        return condition

    success, search_returned_results = await wait_for(new_embedding_model_available(), logger=logger)
    assert success is True, "embedding migration task did not finish on time"
    assert (
        search_returned_results is True
    ), "expected to be able to search with the new embedding model but nucliadb didn't return resources"


@backoff.on_exception(backoff.constant, AssertionError, max_tries=5, interval=5)
async def run_test_find(regional_api_config, ndb: AsyncNucliaDBClient, logger: Logger):
    kb = AsyncNucliaKB()

    result = await kb.search.find(
        ndb=ndb,
        autofilter=True,
        rephrase=True,
        reranker="predict",
        features=["keyword", "semantic", "relations"],
        query=TEST_CHOCO_QUESTION,
    )
    assert result.resources
    first_resource = next(iter(result.resources.values()))
    assert first_resource.slug == "chocolatier"


@backoff.on_exception(backoff.constant, AssertionError, max_tries=5, interval=5)
async def run_test_ask(regional_api_config, ndb: AsyncNucliaDBClient, logger: Logger):
    kb = AsyncNucliaKB()

    ask_result = await kb.search.ask(
        ndb=ndb,
        autofilter=True,
        rephrase=True,
        reranker="predict",
        features=["keyword", "semantic", "relations"],
        query=TEST_CHOCO_QUESTION,
        generative_model="chatgpt-azure-4o-mini",
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
        generative_model="chatgpt-azure-4o-mini",
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
                    query=ActivityLogsChatQuery(
                        year_month=f"{now.year}-{now.month:02}",
                        filters={},
                        pagination=Pagination(limit=100),
                    ),
                )
            )
            if len(logs.data) >= 2:
                # as the asks may be retried more than once (because some times rephrase doesn't always work)
                # we need to check the last logs. The way the tests are setup if we reach here is because we
                # validated that we got the expected results on ask, so the log should match this reasoning.
                if (
                    logs.data[-2].question == TEST_CHOCO_QUESTION
                    and logs.data[-1].question == TEST_CHOCO_ASK_MORE
                ):
                    return (True, logs)
            return (False, None)

        return condition

    success, logs = await wait_for(activity_log_is_stored(), max_wait=120, logger=logger)
    assert success, "Activity logs didn't get stored in time"

    # if we have the ask events, we'll must have the find ones, as they have been done earlier.
    logs = await asyncio.to_thread(
        partial(
            kb.logs.query,
            ndb=ndb,
            type=EventType.SEARCH,
            query=ActivityLogsSearchQuery(
                year_month=f"{now.year}-{now.month:02}", filters={}, pagination=Pagination(limit=100)
            ),
        )
    )

    assert logs.data[-1].question == TEST_CHOCO_QUESTION


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
async def test_kb(request: pytest.FixtureRequest, regional_api_config, clean_kb_test):
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

    zone = regional_api_config["zone_slug"]
    account = regional_api_config["permanent_account_id"]
    auth = get_auth()

    # Creates a brand new kb that will be used troughout this test
    kbid = await run_test_kb_creation(regional_api_config, logger)

    # Configures a nucliadb client defaulting to a specific kb, to be used
    # to override all the sdk endpoints that automagically creates the client
    # as this is incompatible with the cooperative tests
    async_ndb = get_async_kb_ndb_client(zone, account, kbid, user_token=auth._config.token)
    sync_ndb = get_sync_kb_ndb_client(zone, account, kbid, user_token=auth._config.token)

    # Import a preexisting export containing several resources (coming from the financial-news kb)
    # and wait for the resources to be completely imported
    await run_test_import_kb(regional_api_config, async_ndb, logger)

    # Create a labeller configuration, with the goal of testing two tings:
    # - labelling of existing resources (the ones imported)
    # - labelling of new resources(will be created later)
    #
    # Add a new embedding model to the KB and start a task to compute all data
    # with the new embedding model. This will test the data flow between
    # nucliadb and learning to stream all KB data to reprocess with the new
    # embedding model and ingest/index in nucliadb again
    (_, embedding_migration_task_id) = await asyncio.gather(
        run_test_create_da_labeller(regional_api_config, sync_ndb, logger),
        run_test_start_embedding_model_migration_task(sync_ndb, async_ndb),
    )

    # Upload a new resource and validate that is correctly processed and stored in nuclia
    # Also check that its index are available, by checking the amount of extracted paragraphs
    await run_test_upload_and_process(regional_api_config, async_ndb, logger)

    # Wait for both labeller task results to be consolidated in nucliadb while we also run semantic search
    # This /find and /ask requests are crafted so they trigger all the existing calls to predict features
    # We wait until find succeeds to run the ask tests to maximize the chances that all indexes will be
    # available and so minimize the llm costs retrying
    await asyncio.gather(
        run_test_check_da_labeller_output(regional_api_config, sync_ndb, logger),
        run_test_check_embedding_model_migration(sync_ndb, async_ndb, embedding_migration_task_id, logger),
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
