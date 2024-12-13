import pytest
from nuclia.sdk.kb import AsyncNucliaKB, NucliaKB
from nuclia.sdk.kbs import NucliaKBS
from pathlib import Path
from nucliadb_models.metadata import ResourceProcessingStatus
from functools import wraps, partial
from time import monotonic
from nuclia_models.worker.tasks import TaskName, ApplyOptions, DataAugmentation
from nuclia_models.worker.proto import (
    ApplyTo,
    Filter,
    Operation,
    Label,
    LLMConfig,
    LabelOperation,
)
from nucliadb_sdk.v2.exceptions import NotFoundError

import backoff
import asyncio

ASSETS_FILE_PATH = f"{Path(__file__).parent.parent}/assets"


@pytest.mark.asyncio
async def wait_for(condition, max_wait=60, interval=1):
    func_name = condition.__name__
    print(f"start wait_for '{func_name}', max_wait={max_wait}s")
    start = monotonic()
    success = await condition()
    while not success and monotonic() - start < max_wait:
        asyncio.sleep(interval)
        success = await condition()
    print(f"wait_for '{func_name}' success={success} in {monotonic()-start} seconds")
    return success


@pytest.mark.asyncio
async def get_kbid_from_slug(slug: str) -> str:
    kbs = NucliaKBS()
    all_kbs = await asyncio.to_thread(kbs.list)
    kbids_by_slug = {kb.slug: kb.id for kb in all_kbs}
    kbid = kbids_by_slug.get(slug)
    return kbid


@pytest.mark.asyncio
async def run_test_kb_creation(regional_api_config):
    kbs = NucliaKBS()
    new_kb = await asyncio.to_thread(partial(kbs.add, slug=regional_api_config["test_kb_slug"], sentence_embedder="en-2024-04-24"))

    kbid = await get_kbid_from_slug(regional_api_config["test_kb_slug"])
    assert kbid is not None
    kbs.default(kbid)
    print(f"Created kb {new_kb['id']}")


@pytest.mark.asyncio
async def run_test_upload_and_process(regional_api_config):

    kb = AsyncNucliaKB()
    rid = await kb.resource.create(
        title="How this chocolatier is navigating an unexpected spike in cocoa prices",
        slug="chocolatier",
    )
    await kb.upload.file(
        rid=rid, path=f"{ASSETS_FILE_PATH}/chocolatier.html", field="file"
    )

    # Wait for resource to be processed
    def resource_is_processed(rid):
        @wraps(resource_is_processed)
        async def condition():
            resource = await kb.resource.get(rid=rid)
            return resource.metadata.status == ResourceProcessingStatus.PROCESSED

        return condition

    assert await wait_for(resource_is_processed(rid)), "File was not processed in time"


@pytest.mark.asyncio
async def run_test_import_kb(regional_api_config):
    """
    Imports a kb with three resources and some labelsets already created
    """
    kb = AsyncNucliaKB()
    await kb.imports.start(
        path=f"{ASSETS_FILE_PATH}/e2e.financial.mini.export"
    )

    def resources_are_imported(resources):
        @wraps(resources_are_imported)
        async def condition():
            for slug in resources:
                try:
                    await kb.resource.get(slug=slug)
                except NotFoundError:
                    return False
            return True

        return condition

    assert await wait_for(
        resources_are_imported(["disney", "hp", "vaccines"])
    ), "Expected imported resources not found"


@pytest.mark.asyncio
async def run_test_create_da_labeller(regional_api_config):
    """
    Creates a config to run on all current resources and on all future ones
    """
    kb = NucliaKB()
    await asyncio.to_thread(partial(
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
    ))


@pytest.mark.asyncio
async def run_test_check_da_labeller_results(regional_api_config):
    kb = NucliaKB()

    expected_resource_labels = [
        ("disney", ("topic", "MEDIA")),
        ("hp", ("topic", "TECH")),
        ("chocolatier", ("topic", "FOOD")),
        ("vaccines", ("topic", "HEALTH")),
    ]

    def resources_are_labelled(expected):
        @wraps(resources_are_labelled)
        async def condition():
            result = False
            for resource_slug, (labelset, label) in expected:
                try:
                    res = kb.resource.get(
                        slug=resource_slug, show=["extracted"]
                    )
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
                        return False
            return result

        return condition

    assert await wait_for(
        resources_are_labelled(expected_resource_labels)
    ), "Expected computed labels not found in resources"


@pytest.mark.asyncio
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


@backoff.on_exception(backoff.constant, AssertionError, max_tries=10, interval=0)
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


@pytest.mark.asyncio
async def run_test_kb_deletion(regional_api_config):
    kbs = NucliaKBS()
    print("deleting " + regional_api_config["test_kb_slug"])
    await asyncio.to_thread(partial(kbs.delete, slug=regional_api_config["test_kb_slug"]))

    kbid = await get_kbid_from_slug(regional_api_config["test_kb_slug"])
    assert kbid is None


@pytest.mark.asyncio
async def test_kb(regional_api_config, clean_kb_test):
    await run_test_kb_creation(regional_api_config)
    await run_test_import_kb(regional_api_config)
    await run_test_create_da_labeller(regional_api_config)
    await run_test_upload_and_process(regional_api_config),
    await asyncio.gather(
        run_test_check_da_labeller_results(regional_api_config),
        run_test_find(regional_api_config),
        run_test_ask(regional_api_config)
    )
