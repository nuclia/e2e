from collections.abc import Awaitable
from collections.abc import Callable
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from functools import wraps
from nuclia.data import get_auth
from nuclia.lib.kb import AsyncNucliaDBClient
from nuclia.sdk.kb import AsyncNucliaKB
from nuclia.sdk.kbs import AsyncNucliaKBS
from nuclia_e2e.tests.conftest import GlobalAPI
from nuclia_e2e.tests.conftest import ZoneConfig
from nuclia_e2e.tests.utils import has_generated_field
from nuclia_e2e.utils import ASSETS_FILE_PATH
from nuclia_e2e.utils import get_async_kb_ndb_client
from nuclia_e2e.utils import get_kbid_from_slug
from nuclia_e2e.utils import wait_for
from nuclia_models.common.pagination import Pagination
from nuclia_models.events.activity_logs import ActivityLogsAskQuery
from nuclia_models.events.activity_logs import ActivityLogsSearchQuery
from nuclia_models.events.activity_logs import EventType
from nuclia_models.events.activity_logs import QueryFiltersAsk
from nuclia_models.worker.proto import ApplyTo
from nuclia_models.worker.proto import AskOperation
from nuclia_models.worker.proto import Filter
from nuclia_models.worker.proto import Label
from nuclia_models.worker.proto import LabelOperation
from nuclia_models.worker.proto import LLMConfig
from nuclia_models.worker.proto import Operation
from nuclia_models.worker.tasks import ApplyOptions
from nuclia_models.worker.tasks import DataAugmentation
from nuclia_models.worker.tasks import SemanticModelMigrationParams
from nuclia_models.worker.tasks import TaskName
from nuclia_models.worker.tasks import TaskResponse
from nucliadb_models import TextField
from nucliadb_models import UserClassification
from nucliadb_models import UserMetadata
from nucliadb_models.graph.requests import GraphNodesSearchRequest
from nucliadb_models.graph.requests import GraphRelationsSearchRequest
from nucliadb_models.graph.requests import GraphSearchRequest
from nucliadb_models.metadata import ResourceProcessingStatus
from nucliadb_models.search import Image
from nucliadb_sdk.v2.exceptions import ClientError
from nucliadb_sdk.v2.exceptions import NotFoundError
from textwrap import dedent
from typing import Any

import asyncio
import backoff
import base64
import pytest

Logger = Callable[[str], None]

TEST_CHOCO_QUESTION = "why are cocoa prices high?"
TEST_CHOCO_ASK_MORE = "how has this impacted customers?"


async def run_test_kb_creation(regional_api_config, kb_slug, logger: Logger) -> str:
    kbs = AsyncNucliaKBS()
    new_kb = await kbs.add(
        zone=regional_api_config.zone_slug,
        slug=kb_slug,
        learning_configuration={"semantic_models": ["en-2024-04-24"]},
    )

    kbid = await get_kbid_from_slug(regional_api_config.zone_slug, kb_slug)
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

    success, _ = await wait_for(resource_is_processed(rid), max_wait=180, interval=10, logger=logger)
    assert success, "File was not processed in time, PROCESSED status not found in resource"

    # Wait for resource to be indexed by searching for a resource based on a content that just
    # the paragraph we're looking for contains
    def resource_is_indexed(rid):
        @wraps(resource_is_indexed)
        async def condition() -> tuple[bool, Any]:
            result = await kb.search.find(ndb=ndb, features=["keyword"], reranker="noop", query="Michiko")
            return len(result.resources) > 0, None

        return condition

    success, _ = await wait_for(resource_is_indexed(rid), logger=logger, max_wait=120, interval=1)
    assert success, "File was not indexed in time, not enough paragraphs found on resource"


async def run_test_import_kb(regional_api_config, ndb: AsyncNucliaDBClient, logger: Logger):
    """
    Imports a kb with three resources and some labelsets already created
    """
    kb = AsyncNucliaKB()

    response = await kb.imports.start(path=f"{ASSETS_FILE_PATH}/e2e.financial.mini.export", ndb=ndb)
    logger(f"Import started with id {response.import_id}")

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


async def run_test_da_ask_worker(regional_api_config, ndb: AsyncNucliaDBClient, logger: Logger) -> str:
    """
    Creates a config to run on all current resources and on all future ones
    """
    kb = AsyncNucliaKB()
    tr: TaskResponse = await kb.task.start(
        ndb=ndb,
        task_name=TaskName.ASK,
        apply=ApplyOptions.ALL,
        parameters=DataAugmentation(
            name="test-ask",
            on=ApplyTo.FIELD,
            filter=Filter(),
            operations=[
                Operation(
                    ask=AskOperation(
                        question="What is the document about? Summarize it in a single sentence.",
                        destination="customsummary",
                    )
                )
            ],
            llm=LLMConfig(model="chatgpt-azure-4o-mini"),
        ),
    )
    return tr.id


async def run_test_check_da_ask_output(
    regional_api_config, ask_task_id: str, ndb: AsyncNucliaDBClient, logger: Logger
):
    kb = AsyncNucliaKB()

    resource_slugs = [
        "disney",
        "hp",
        "chocolatier",
        "vaccines",
    ]

    # The expected field id for the generated field. This should match the
    # `destination` field in the AskOperation above: `da-{destination}`
    expected_field_id_prefix = "da-customsummary"

    def resources_have_generated_fields(resource_slugs):
        @wraps(resources_have_generated_fields)
        async def condition() -> tuple[bool, Any]:
            resources_have_field = await asyncio.gather(
                *[
                    has_generated_field(ndb, kb, resource_slug, expected_field_id_prefix)
                    for resource_slug in resource_slugs
                ]
            )
            result = all(resources_have_field)
            return (result, None)

        return condition

    success, _ = await wait_for(
        condition=resources_have_generated_fields(resource_slugs),
        max_wait=5 * 60,  # 5 minutes
        interval=20,
        logger=logger,
    )
    assert success, f"Expected generated text fields not found in resources. task_id: {ask_task_id}"

    # Now schedule the cleanup and make sure that all custom-summary fields are gone.
    await kb.task.delete(
        ndb=ndb,
        task_id=ask_task_id,
        cleanup=True,
    )

    def generated_fields_deleted_from_resources(resource_slugs):
        @wraps(generated_fields_deleted_from_resources)
        async def condition() -> tuple[bool, Any]:
            resources_have_field = await asyncio.gather(
                *[
                    has_generated_field(ndb, kb, resource_slug, expected_field_id_prefix)
                    for resource_slug in resource_slugs
                ]
            )
            result = not any(resources_have_field)
            return (result, None)

        return condition

    success, _ = await wait_for(
        condition=generated_fields_deleted_from_resources(resource_slugs),
        max_wait=5 * 60,  # 5 minutes
        interval=20,
        logger=logger,
    )
    assert success, f"Generated fields have not been deleted from resources. task_id: {ask_task_id}"


async def run_test_create_da_labeller(regional_api_config, ndb: AsyncNucliaDBClient, logger: Logger):
    """
    Creates a config to run on all current resources and on all future ones
    """
    kb = AsyncNucliaKB()
    await kb.task.start(
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


async def run_test_check_da_labeller_output(regional_api_config, ndb: AsyncNucliaDBClient, logger: Logger):
    kb = AsyncNucliaKB()

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
                    res = await kb.resource.get(slug=resource_slug, show=["extracted"], ndb=ndb)
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

    success, _ = await wait_for(resources_are_labelled(expected_resource_labels), logger=logger)
    assert success, "Expected computed labels not found in resources"


async def run_test_create_da_labeller_with_label_filter(
    regional_api_config, ndb: AsyncNucliaDBClient, logger: Logger
):
    """
    Creates a config to run on all future ones but only on resources matching a specific classification label
    """
    kb = AsyncNucliaKB()
    # Create the task
    await kb.task.start(
        ndb=ndb,
        task_name=TaskName.LABELER,
        apply=ApplyOptions.NEW,
        parameters=DataAugmentation(
            name="test-labels-filter",
            on=ApplyTo.FIELD,
            filter=Filter(
                labels=[
                    "MyLabels/LABEL1",
                ]
            ),
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
                                label="CLIMBING",
                                description="Related to financial news in the CLIMBING industry",
                            ),
                        ],
                        ident="topic-filtered",
                        description="Topic of the article in the financial context",
                    )
                )
            ],
            llm=LLMConfig(model="chatgpt-azure-4o-mini"),
        ),
    )

    title = "The rise of climbing gyms across the US"
    text = """The rise of climbing gyms across the US has been a boon for the climbing industry.
    With the rise of climbing gyms, more people are getting into the sport and the industry is growing.
    Items like climbing shoes, ropes, and harnesses are flying off the shelves as more people take up the sport."""  # noqa: E501
    article = TextField(body=text)

    # Create a resource talking about climbing that contains the label that should trigger the labeller agent
    await kb.resource.create(
        ndb=ndb,
        title=title,
        slug="climbing-with-label",
        usermetadata=UserMetadata(classifications=[UserClassification(labelset="MyLabels", label="LABEL1")]),
        texts={"article": article},
    )

    # Create a resource talking about climbing that does not contain the label
    # that should NOT trigger the labeller agent
    await kb.resource.create(
        ndb=ndb,
        title=title,
        slug="climbing-without-label",
        texts={"article": article},
    )


async def run_test_check_da_labeller_with_label_filter_output(
    regional_api_config, ndb: AsyncNucliaDBClient, logger: Logger
):
    kb = AsyncNucliaKB()

    def filtered_resource_is_labelled():
        @wraps(filtered_resource_is_labelled)
        async def condition() -> tuple[bool, None]:
            async def resource_augmented(slug: str) -> bool:
                try:
                    res = await kb.resource.get(slug=slug, show=["extracted"], ndb=ndb)
                except NotFoundError:
                    # some resource may still be missing from nucliadb, let's wait more
                    return False
                for fc in res.computedmetadata.field_classifications:
                    if not (fc.field.field_type.name == "TEXT" and fc.field.field == "article"):
                        continue
                    computed_labels = [(cl.labelset, cl.label) for cl in fc.classifications]
                    return ("topic-filtered", "CLIMBING") in computed_labels
                return False

            labeled_resource_augmented = await resource_augmented("climbing-with-label")
            unlabeled_resource_augmented = await resource_augmented("climbing-without-label")
            return (labeled_resource_augmented and not unlabeled_resource_augmented, None)

        return condition

    success = await wait_for(filtered_resource_is_labelled(), logger=logger)
    assert success, "Expected computed label not found in filtered resource"


async def run_test_start_embedding_model_migration_task(ndb: AsyncNucliaDBClient) -> str:
    kbid = ndb.kbid

    # XXX: this is a really naive way to select a self-hosted model for a KB
    # without listing learning_config. At some point, we should implement
    # something smarter.
    #
    # This model names are coupled with learning_models library and a change
    # there could break this test
    vectorsets = await ndb.ndb.list_vector_sets(kbid=kbid)
    assert len(vectorsets.vectorsets) == 1
    current_model = vectorsets.vectorsets[0].id
    new_model = "multilingual-2024-05-06" if current_model == "en-2024-04-24" else "en-2024-04-24"

    # we first need to add the new embedding model in the KB
    created = await ndb.ndb.add_vector_set(kbid=kbid, vectorset_id=new_model)
    vectorset_id = created.id

    # now we can add a migration task that will reprocess all KB data with the
    # new model and store it in nucliadb
    kb = AsyncNucliaKB()
    task = await kb.task.start(
        ndb=ndb,
        task_name=TaskName.SEMANTIC_MODEL_MIGRATOR,
        apply=ApplyOptions.ALL,
        parameters=SemanticModelMigrationParams(
            semantic_model_id=vectorset_id,
        ),
    )

    return task.id


async def run_test_check_embedding_model_migration(ndb: AsyncNucliaDBClient, task_id: str, logger: Logger):
    def new_embedding_model_available() -> Callable[[], Awaitable[tuple[bool, bool | None]]]:
        @wraps(new_embedding_model_available)
        async def condition() -> tuple[bool, bool | None]:
            search_returned_results = False
            kb = AsyncNucliaKB()

            task = await kb.task.get(ndb=ndb, task_id=task_id)
            if not task.request.completed:
                # we have to wait until task has finished to try if it worked
                return (False, search_returned_results)

            new_model = task.request.parameters.semantic_model_id

            # once finished, let's try a fast /find and validate there are
            # results with the new semantic model
            result = await kb.search.find(
                ndb=ndb,
                rephrase=False,
                reranker="noop",
                features=["semantic"],
                vectorset=new_model,
                query=TEST_CHOCO_QUESTION,
            )
            search_returned_results = bool(result.resources)
            return (True, search_returned_results)

        return condition

    success, search_returned_results = await wait_for(
        new_embedding_model_available(), max_wait=200, logger=logger
    )
    assert success is True, "embedding migration task did not finish on time"
    assert (
        search_returned_results is True
    ), "expected to be able to search with the new embedding model but nucliadb didn't return resources"


@backoff.on_exception(backoff.constant, (AssertionError, ClientError), max_tries=5, interval=5)
async def run_test_find(ndb: AsyncNucliaDBClient):
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
async def run_test_graph(ndb: AsyncNucliaDBClient, kbid: str):
    paths = await ndb.ndb.graph_search(
        kbid=kbid,
        content=GraphSearchRequest.model_validate(
            {
                "query": {
                    "prop": "path",
                    "source": {
                        "value": "Apple",
                    },
                    "destination": {"value": "China"},
                }
            }
        ),
    )
    assert len(paths.paths) > 0

    nodes = await ndb.ndb.graph_nodes(
        kbid=kbid,
        content=GraphNodesSearchRequest.model_validate({"query": {"prop": "node", "value": "Apple"}}),
    )
    assert len(nodes.nodes) > 0

    relations = await ndb.ndb.graph_relations(
        kbid=kbid,
        content=GraphRelationsSearchRequest.model_validate(
            {"query": {"prop": "relation", "label": "operating system"}}
        ),
    )
    assert len(relations.relations) > 0


@backoff.on_exception(backoff.constant, (AssertionError, ClientError), max_tries=5, interval=5)
async def run_test_ask(ndb: AsyncNucliaDBClient):
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
    # It increased the price of its permanent collection of chocolate bars
    # from $13 to $14 and raised the price of its bonbons by 7%-8%.
    assert "14" in ask_more_result.answer.decode().lower()


@backoff.on_exception(backoff.constant, (AssertionError, ClientError), max_tries=5, interval=5)
async def run_test_ask_query_image(ndb: AsyncNucliaDBClient):
    kb = AsyncNucliaKB()
    image_path = f"{ASSETS_FILE_PATH}/cocoabeans.png"
    with open(image_path, "rb") as image_file:
        image_data = base64.b64encode(image_file.read()).decode("utf-8")
    ask_result = await kb.search.ask(
        ndb=ndb,
        autofilter=True,
        rephrase=True,
        reranker="predict",
        features=["keyword", "semantic", "relations"],
        query="Why are prices for this item high?",
        generative_model="chatgpt-azure-4o-mini",
        prompt=dedent(
            """
            Answer the following question based **only** on the provided context and image.
             Do **not** use any outside knowledge.
             If the context does not provide enough information to fully answer the question,
            reply with: “Not enough data to answer this.”
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
        query_image=Image(
            content_type="image/png",
            b64encoded=image_data,
        ),
    )
    assert "climate change" in ask_result.answer.decode().lower()


async def run_test_activity_log(regional_api_config, ndb, logger):
    kb = AsyncNucliaKB()
    now = datetime.now(tz=timezone.utc)

    def activity_log_is_stored():
        @wraps(activity_log_is_stored)
        async def condition() -> tuple[bool, Any]:
            logs = await kb.logs.query(
                ndb=ndb,
                type=EventType.ASK,
                query=ActivityLogsAskQuery(
                    year_month=f"{now.year}-{now.month:02}",
                    filters=QueryFiltersAsk(),  # type: ignore[call-arg]
                    pagination=Pagination(limit=100),
                ),
            )
            print(f"activity_log_is_stored -----> {len(logs.data)}")
            if len(logs.data) >= 2:
                # as the asks may be retried more than once (because some times rephrase doesn't always work)
                # we need to check the last logs. The way the tests are setup if we reach here is because we
                # validated that we got the expected results on ask, so the log should match this reasoning.
                if (
                    logs.data[-2].question == TEST_CHOCO_QUESTION
                    and logs.data[-1].question == TEST_CHOCO_ASK_MORE
                ):
                    return (True, logs)
                from pprint import pprint
                print("----------------------------")
                pprint(logs.data)
                print("----------------------------")
            return (False, None)

        return condition

    success, logs = await wait_for(activity_log_is_stored(), max_wait=360, logger=logger)
    assert success, "Activity logs didn't get stored in time"

    # if we have the ask events, we'll must have the find ones, as they have been done earlier.
    logs = await kb.logs.query(
        ndb=ndb,
        type=EventType.SEARCH,
        query=ActivityLogsSearchQuery(
            year_month=f"{now.year}-{now.month:02}", filters={}, pagination=Pagination(limit=100)
        ),
    )

    assert logs.data[-1].question == TEST_CHOCO_QUESTION


async def run_test_remi_query(regional_api_config, ndb, logger):
    kb = AsyncNucliaKB()
    starting_at = datetime.now(tz=timezone.utc) - timedelta(
        seconds=600
    )  # 10 minutes is longer than we need, indicating a "safe start" indicator for this test run
    to = starting_at + timedelta(hours=1)

    def remi_data_is_computed():
        @wraps(remi_data_is_computed)
        async def condition() -> tuple[bool, Any]:
            scores = await kb.remi.get_scores(
                ndb=ndb,
                starting_at=starting_at,
                to=to,
                aggregation="day",
            )
            if len(scores[0].metrics) > 0:
                return (True, scores)
            return (False, None)

        return condition

    _, success = await wait_for(remi_data_is_computed(), max_wait=180, logger=logger)
    assert success, "Remi scores didn't get computed in time"


async def run_test_tokens_on_activity_log(
    ndb: AsyncNucliaDBClient, expected_accounting_tokens: float, logger
):
    kb = AsyncNucliaKB()

    def nuclia_tokens_calculated_on_activity_log():
        @wraps(nuclia_tokens_calculated_on_activity_log)
        async def condition() -> tuple[bool, Any]:
            now = datetime.now(tz=timezone.utc)
            logs = await kb.logs.query(
                ndb=ndb,
                type=EventType.ASK,
                query=ActivityLogsAskQuery(
                    year_month=f"{now.year}-{now.month:02}",
                    filters=QueryFiltersAsk(),  # type: ignore[call-arg]
                    pagination=Pagination(limit=100),
                    show={"nuclia_tokens"},
                ),
            )
            if len(logs.data) > 0:
                nuclia_tokens = logs.data[-1].nuclia_tokens
                if nuclia_tokens is not None and nuclia_tokens > 0:
                    return (True, nuclia_tokens)
            return (False, None)

        return condition

    success, activity_log_nuclia_tokens = await wait_for(
        nuclia_tokens_calculated_on_activity_log(), max_wait=300, logger=logger
    )
    assert success, "Nuclia tokens were not added to activity log event on time"
    assert activity_log_nuclia_tokens > 0
    assert activity_log_nuclia_tokens == expected_accounting_tokens


async def run_test_tokens_on_accounting(global_api: GlobalAPI, account: str, kbid: str, logger):
    def nuclia_tokens_stored_on_accounting():
        @wraps(nuclia_tokens_stored_on_accounting)
        async def condition() -> tuple[bool, Any]:
            # IMPORTANT! The usage endpoint is cached using the request parameters, so i'ts mandatory
            # to change the date in each attempt
            now = datetime.now(tz=timezone.utc)
            from_date = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            to_date = (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

            result = await global_api.get_usage(account, kbid, from_date, to_date)
            metrics = list(filter(lambda m: m["name"] == "nuclia_tokens_billed", result[0]["metrics"]))
            if not metrics:
                return (False, None)
            nuclia_tokens = metrics[0]["value"]
            if nuclia_tokens > 0:
                return (True, nuclia_tokens)
            return (False, None)

        return condition

    success, accouting_nuclia_tokens = await wait_for(
        nuclia_tokens_stored_on_accounting(), max_wait=600, interval=10, logger=logger
    )
    assert success, "Nuclia tokens were not received by accounting on time"
    return accouting_nuclia_tokens


async def run_test_kb_deletion(regional_api_config, kbid, kb_slug, logger):
    kbs = AsyncNucliaKBS()
    logger("deleting " + kbid)
    await kbs.delete(zone=regional_api_config.zone_slug, id=kbid)

    kbid = await get_kbid_from_slug(regional_api_config.zone_slug, kb_slug)
    assert kbid is None


@pytest.mark.asyncio_cooperative
async def test_kb_features(request: pytest.FixtureRequest, regional_api_config):
    """
    This test simulates a typical sequence of operations within a KnowledgeBox (KB).

    Instead of breaking these into separate atomic tests, we run them together to optimize resource usage.
    Creating a new KB for each atomic test would be inefficient, so this approach allows us to test
    functionality on a freshly created KB without excessive overhead. The key advantage of testing on a new
    KB is the ability to catch errors that might not appear when using an existing KB with older parameters.

    The test consists of both sequential and concurrent operations. Some steps must be executed in sequence
    to ensure the correct state before proceeding, while others can run in parallel. This is why we utilize
    gather in certain parts of the test.
    """

    def logger(msg):
        print(f"{request.node.name} ::: {msg}")

    zone = regional_api_config.zone_slug
    auth = get_auth()
    kb_slug = f"{regional_api_config.test_kb_slug}-test_kb_features"

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
    # embedding model and ingest/index in nucliadb again.
    # We want to do it before upload to validate, on one side the migration
    # itself, and on the other ingestion in a KB with multiple vectorsets
    #
    # Create a labeller configuration that runs only on new resources that have a specific label
    # This will test the filtering capabilities of the labeller
    #
    (_, embedding_migration_task_id, _, ask_task_id) = await asyncio.gather(
        run_test_create_da_labeller(regional_api_config, async_ndb, logger),
        run_test_start_embedding_model_migration_task(async_ndb),
        run_test_create_da_labeller_with_label_filter(regional_api_config, async_ndb, logger),
        run_test_da_ask_worker(regional_api_config, async_ndb, logger),
    )

    # Upload a new resource and validate that is correctly processed and stored in nuclia
    # Also check that its index are available, by checking the amount of extracted paragraphs
    await run_test_upload_and_process(regional_api_config, async_ndb, logger)

    # Wait for both labeller task results to be consolidated in nucliadb while we also run semantic search
    # This /find and /ask requests are crafted so they trigger all the existing calls to predict features
    # We wait until find succeeds to run the ask tests to maximize the chances that all indexes will be
    # available and so minimize the llm costs retrying
    await asyncio.gather(
        run_test_check_da_labeller_output(regional_api_config, async_ndb, logger),
        run_test_check_embedding_model_migration(async_ndb, embedding_migration_task_id, logger),
        run_test_find(async_ndb),
        run_test_graph(async_ndb, kbid),
        run_test_check_da_labeller_with_label_filter_output(regional_api_config, async_ndb, logger),
        run_test_check_da_ask_output(regional_api_config, ask_task_id, async_ndb, logger),
    )
    await asyncio.gather(
        run_test_ask(async_ndb),
        run_test_ask_query_image(async_ndb),
    )

    # Validate that all the data about the usage we generated is correctly stored on the activity log
    # and can be queried, and that the remi quality metrics. Even if the remi metrics won't be computed until
    # the activity log is stored, the test_activity_log tests several things aside the ask events (the ones
    # affecting the remi queries) and so we can benefit of running them in parallel.
    await asyncio.gather(
        run_test_activity_log(regional_api_config, async_ndb, logger),
        run_test_remi_query(regional_api_config, async_ndb, logger),
    )

    # Delete the kb as a final step
    await run_test_kb_deletion(regional_api_config, kbid, kb_slug, logger)


@pytest.mark.asyncio_cooperative
async def test_kb_usage(
    request: pytest.FixtureRequest, regional_api_config: ZoneConfig, global_api: GlobalAPI
):
    """
    This test is conducted separately from the main test_kb to ensure more deterministic results. The retries
    that typically occur in test_kb make it difficult to achieve the level of precision required for this
    validation.

    In this test, the actual response from the ask endpoint is not relevant—as long as the request consumes
    input tokens, the test remains valid. The primary objective is to verify that all usage data generated by
    an ask request is properly collected and integrated into the audit event. This includes tracking data from
    NucliaDB, Predict, and ensuring it aligns with the data recorded by Accounting.

    Since usage tracking is performed on a per-request basis, this test assumes that only a single request is
    being made and that the data captured by Accounting corresponds solely to that request.
    """

    def logger(msg):
        print(f"{request.node.name} ::: {msg}")

    zone = regional_api_config.zone_slug
    assert regional_api_config.global_config is not None
    account = regional_api_config.global_config.permanent_account_id  # noqa: F841
    auth = get_auth()
    kb_slug = f"{regional_api_config.test_kb_slug}-test_kb_usage"

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

    # Import a preexisting export containing several resources (coming from the financial-news kb)
    # and wait for the resources to be completely imported
    await run_test_import_kb(regional_api_config, async_ndb, logger)

    kb = AsyncNucliaKB()
    await kb.search.ask(
        ndb=async_ndb,
        rephrase=True,
        reranker="predict",
        features=["keyword", "semantic", "relations"],
        query=TEST_CHOCO_QUESTION,
        generative_model="chatgpt-azure-4o-mini",
    )

    # ⚠️⚠️⚠️ WARNING
    # Disabled test as this subtest used root access to be able to query any account usage stats
    # Enable again when we have some alternate way of doing this
    # ⚠️⚠️⚠️
    # accounting_tokens = await run_test_tokens_on_accounting(global_api, account, kbid, logger)
    # Disable check nuclia tokens on activity log for now, as under heavy loads it takes several hours
    # to be up to date, and so the logs won't be available on most of the tests runs.
    # await run_test_tokens_on_activity_log(async_ndb, accounting_tokens, logger)

    # Delete the kb as a final step
    await run_test_kb_deletion(regional_api_config, kbid, kb_slug, logger)
