from collections.abc import Callable
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from functools import wraps
import urllib.error
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
from pathlib import Path
from prometheus_client import CollectorRegistry
from prometheus_client import Gauge
from prometheus_client import push_to_gateway
from textwrap import dedent
from typing import Any
import urllib
import backoff
import os
import pytest
import yaml
import json

Logger = Callable[[str], None]

TEST_CHOCO_QUESTION = "why are cocoa prices high?"
TEST_CHOCO_ASK_MORE = "When did they start being high?"
GHA_RUN_ID = os.getenv("GHA_RUN_ID", "unknown")
PROMETHEUS_PUSHGATEWAY = os.getenv(
    "PROMETHEUS_PUSHGATEWAY", "http://prometheus-cloud-pushgateway-prometheus-pushgateway:9091"
)
CORE_APPS_REPO_PATH = os.getenv("CORE_APPS_REPO_PATH", "/tmp/core-apps")


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
    def __init__(self, desc):
        self.desc: str = desc
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


def push_timings_to_prometheus(
    timings: dict[str, Timer],
    job_name: str,
    instance: str,
    benchmark_type: str,
    cluster: str,
    extra_labels: dict[str, str] = None,
    gateway_url: str = PROMETHEUS_PUSHGATEWAY,
):
    registry = CollectorRegistry()

    base_labels = {
        "benchmark_type": benchmark_type,
        "k8s_cluster": cluster,
        "step": "",  # Placeholder, set dynamically below
    }
    if extra_labels:
        base_labels.update(extra_labels)

    # Create a gauge with dynamic label names
    label_names = list(base_labels.keys())
    g = Gauge(
        name="benchmark_step_duration_seconds",
        documentation="Elapsed time for each step in benchmark (in seconds)",
        labelnames=label_names,
        registry=registry,
    )

    for step_name, timer in timings.items():
        labels = base_labels.copy()
        labels["step"] = step_name
        g.labels(**labels).set(timer.elapsed)

    # Push to Pushgateway
    push_to_gateway(gateway_url, job=job_name, grouping_key={"instance": instance}, registry=registry)


def get_application_set_version(file_path, cluster):
    try:
        with Path(file_path).open() as file:
            yaml_data = yaml.safe_load(file)
            versions = {
                item["cluster"]: item["app_chart_version"]
                for item in yaml_data["spec"]["generators"][0]["list"]["elements"]
            }
            if cluster not in versions:
                raise RuntimeError(f"Cluster {cluster} not defined in {file_path}")
            return versions[cluster]
    except FileNotFoundError as exc:
        err_msg = f"ApplicationSet not found at {file_path}, refresh local repos"
        raise RuntimeError(err_msg) from exc


def extract_versions(components, cluster):
    versions = {}
    for component_name in components:
        app_set_file = f"{CORE_APPS_REPO_PATH}/apps/{component_name}.applicationSet.yaml"
        label_component_name = component_name.replace("-", "_")
        versions[label_component_name] = get_application_set_version(app_set_file, cluster)
    return versions


@pytest.mark.skipif(os.getenv("BENCHMARK") != "1", reason="Benchmark not enabled")
@pytest.mark.asyncio_cooperative
async def test_benchmark_kb_ingestion(request: pytest.FixtureRequest, regional_api_config):
    """
    This test ferforms the minimal operations too upload a file and validate that is indexed
    with the purpose of benchmarking the ingestion process
    """
    timings = {
        "upload": Timer("Client perceived upload time"),
        "process_delay": Timer(
            "Time elapsed  since upload finished to processing-slow start. This is a rough metric as the processes involved here (scheduling, processor scale up) may alredy have started before the upload finished from the user perspective"
        ),
        "process": Timer("Real running time of the processor up until the broker message is sent."),
        "ingest": Timer(
            "Elapsed time since processing sent the Broker message until the resource is stored as PROCESSED in nucliadb. This includes: waiting for the BM, storing"
        ),
        "index_ready": Timer("Elapsed time since NucliaDB stored the processed BM until is ready for search"),
    }
    benchmark_env = regional_api_config.global_config.name
    benchmark_cluster = regional_api_config.name

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
            timings["ingest"].stop()
            resources = await kb.list(ndb=async_ndb)
            if len(resources.resources) > 0:
                if resources.resources[0].metadata.status == ResourceProcessingStatus.PROCESSED:
                    resource = await kb.resource.get(
                        rid=resources.resources[0].id, ndb=async_ndb, show=["basic", "extracted"]
                    )
                    return (True, resource)
            return False, None

        return condition

    success, resource = await wait_for(
        first_resource_is_processed(), max_wait=180, interval=0.5, logger=logger
    )
    assert success, "File was not processed in time, PROCESSED status not found in resource"

    # Read timings of processing steps, provided by the processor and stored in extracted metadata
    # last_understanding is the timestamp of the last thing done just before sending the BrokerMessage to NDB
    processing_started = resource.data.files["file"].extracted.metadata.metadata.last_processing_start
    processing_finished = resource.data.files["file"].extracted.metadata.metadata.last_understanding

    timings["process"].start(processing_started)
    timings["process"].stop(processing_finished)

    timings["process_delay"].stop(processing_started)
    timings["ingest"].start(processing_finished)
    timings["index_ready"].start(timings["ingest"].end_time)

    # Wait for resource to be indexed by searching for a resource based on a content that just
    # the paragraph we're looking for contains, if that responds means the new indexed data is ready
    def resource_is_indexed(rid):
        @wraps(resource_is_indexed)
        async def condition() -> tuple[bool, Any]:
            # Considering that if the index is ready, it was before the request started, so keep updating
            # this until is actually true. This will be probably more accurate than waiting for the request to end.
            timings["index_ready"].stop()
            result = await kb.search.find(
                ndb=async_ndb, features=["keyword"], reranker="noop", query="Michiko"
            )
            print(len(result.resources))
            return len(result.resources) > 0, None

        return condition

    success, _ = await wait_for(resource_is_indexed(resource.id), logger=logger, max_wait=60, interval=0.1)
    assert success, "File was not indexed in time, not enough paragraphs found on resource"

    running_versions = extract_versions(
        ["nucliadb_writer", "nucliadb_ingest", "nidx", "processing", "processing-slow"],
        cluster=benchmark_cluster,
    )

    # store running versions
    with Path(f"{benchmark_env}__{benchmark_cluster}__versions.json").open("w") as f:
        json.dump(running_versions, f)

    with Path(f"{benchmark_env}__{benchmark_cluster}__ids.json").open("w") as f:
        json.dump(
            {
                "kbid": kbid,
                "rid": resource.id,
                "grafana_url": regional_api_config.global_config.grafana_url,
                "tempo_datasource_id": regional_api_config.global_config.tempo_datasource_id,
            },
            f,
        )

    # store timings
    with Path(f"{benchmark_env}__{benchmark_cluster}__timings.json").open("w") as f:
        json_timings = {
            timer_name: {"elapsed": f"{timer.elapsed:.3f}", "desc": timer.desc}
            for timer_name, timer in timings.items()
        }
        json.dump(json_timings, f)

    # # Delete the kb as a final step
    # await run_test_kb_deletion(regional_api_config, kbid, kb_slug, logger)

    push_timings_to_prometheus(
        timings=timings,
        job_name="daily_benchmark",
        instance=f"{GHA_RUN_ID}",
        benchmark_type="ingestion",
        cluster=benchmark_cluster,
        extra_labels={f"version_{component}": version for component, version in running_versions.items()},
    )
