from _pytest.mark.structures import ParameterSet
from collections.abc import AsyncGenerator
from collections.abc import Callable
from collections.abc import Coroutine
from dataclasses import dataclass
from nuclia.lib.nua import AsyncNuaClient
from nuclia_e2e.tests.conftest import TEST_ENV, GRAFANA_URL
from nuclia_e2e.utils import get_asset_file_path
from nuclia_models.worker.proto import ApplyTo
from nuclia_models.worker.proto import AskOperation
from nuclia_models.worker.proto import EntityDefinition
from nuclia_models.worker.proto import Filter
from nuclia_models.worker.proto import GraphOperation
from nuclia_models.worker.proto import GuardOperation
from nuclia_models.worker.proto import Label
from nuclia_models.worker.proto import LabelOperation
from nuclia_models.worker.proto import LLMConfig
from nuclia_models.worker.proto import Operation
from nuclia_models.worker.proto import QAOperation
from nuclia_models.worker.tasks import DataAugmentation
from nuclia_models.worker.tasks import PARAMETERS_TYPING
from nuclia_models.worker.tasks import TaskName
from nuclia_models.worker.tasks import TaskStart
from nucliadb_protos.writer_pb2 import BrokerMessage
from typing import Any

import aiofiles
import aiohttp
import asyncio
import base64
import pytest
import json

LLAMA_GUARD_DISABLED = TEST_ENV == "prod"
PROMPT_GUARD_DISABLED = TEST_ENV == "prod"


def get_grafana_task_url(task_id: str) -> str:
    raw = {
        "y0r": {
            "datasource": "P8E80F9AEF21F6940",
            "queries": [
                {
                    "refId": "A",
                    "expr": f'{{pod=~"{task_id}.*"}} |= ``',
                    "queryType": "range",
                    "datasource": {"type": "loki", "uid": "P8E80F9AEF21F6940"},
                    "editorMode": "builder",
                }
            ],
            "range": {"from": "now-24h", "to": "now"},
        }
    }
    query = json.dumps(raw, indent=None, separators=(",", ":"))
    return f"{GRAFANA_URL}/explore?schemaVersion=1&panes={query}&orgId=1"


@dataclass
class TaskTestInput:
    filename: str
    task_name: TaskName
    parameters: PARAMETERS_TYPING
    validate_output: Callable[[BrokerMessage], None]


@pytest.fixture(scope="session")
def aiohttp_client() -> (
    Callable[[str, str | None, str | None, int], Coroutine[Any, Any, aiohttp.ClientSession]]
):
    async def create_aiohttp_client(
        base_url: str,
        nua_key: str | None = None,
        pat_key: str | None = None,
        timeout: int = 30,
    ) -> aiohttp.ClientSession:
        headers = (
            {"X-NUCLIA-NUAKEY": f"Bearer {nua_key}"} if nua_key else {"Authorization": f"Bearer {pat_key}"}
        )
        timeout_config = aiohttp.ClientTimeout(total=timeout)

        # Create the session but return it directly instead of yielding
        session = aiohttp.ClientSession(
            base_url=base_url,
            headers=headers,
            timeout=timeout_config,
        )
        return session  # Return the session instead of yielding

    return create_aiohttp_client  # Return the async function


async def create_nua_key(client: aiohttp.ClientSession, account_id: str, title: str) -> tuple[str, str]:
    body = {
        "title": title,
        "contact": "temporal key, safe to delete",
    }
    resp = await client.post(f"/api/v1/account/{account_id}/nua_clients", json=body)
    assert resp.status == 201, await resp.text()
    nua_response = await resp.json()
    return nua_response["client_id"], nua_response["token"]


async def delete_nua_key(client: aiohttp.ClientSession, account_id: str, nua_client_id: str):
    resp = await client.delete(f"/api/v1/account/{account_id}/nua_client/{nua_client_id}")
    assert resp.status == 204, await resp.text()


def task_done(task_request: dict) -> bool:
    return task_request["failed"] or task_request["completed"]


async def create_dataset(client: aiohttp.ClientSession) -> str:
    dataset_body = {
        "name": "e2e-test-dataset",
        "filter": {"labels": []},
        "type": "FIELD_STREAMING",
    }
    resp = await client.post("/api/v1/datasets", json=dataset_body)
    assert resp.status == 201, await resp.text()
    return (await resp.json())["id"]


async def delete_dataset(client: aiohttp.ClientSession, dataset_id: str):
    resp = await client.delete(f"/api/v1/dataset/{dataset_id}")
    assert resp.status == 204, await resp.text()


async def push_data_to_dataset(client: aiohttp.ClientSession, dataset_id: str, filename: str):
    async with aiofiles.open(get_asset_file_path(filename), "rb") as f:
        content = await f.read()
    resp = await client.put(
        f"/api/v1/dataset/{dataset_id}/partition/1",
        data=content,
    )
    assert resp.status == 204, await resp.text()


async def start_task(
    client: aiohttp.ClientSession,
    dataset_id: str,
    task_name: TaskName,
    parameters: PARAMETERS_TYPING,
) -> str:
    resp = await client.post(
        f"/api/v1/dataset/{dataset_id}/task/start",
        json=TaskStart(name=task_name, parameters=parameters).model_dump(),
    )
    assert resp.status == 200, await resp.text()
    return (await resp.json())["id"]


async def stop_task(client: aiohttp.ClientSession, dataset_id: str, task_id: str):
    resp = await client.post(f"/api/v1/dataset/{dataset_id}/task/{task_id}/stop")
    assert resp.status == 200, await resp.text()


async def delete_task(client: aiohttp.ClientSession, dataset_id: str, task_id: str):
    resp = await client.delete(f"/api/v1/dataset/{dataset_id}/task/{task_id}")
    assert resp.status == 200, await resp.text()


async def wait_for_task_completion(
    client: aiohttp.ClientSession,
    dataset_id: str,
    task_id: str,
    max_duration: int = 300,
):
    start_time = asyncio.get_event_loop().time()
    while True:
        elapsed_time = asyncio.get_event_loop().time() - start_time
        grafana_task_log__url = get_grafana_task_url(task_id)
        if elapsed_time > max_duration:
            raise TimeoutError(
                f"Task {task_id} didn't complete within the maximum allowed time of {max_duration} seconds.\n"
                f"You may find more information on the task log: {grafana_task_log__url}, if you see some"
                "SIGTERM on it, preemtion ocurred and the task won't be retried."
            )

        resp = await client.get(
            f"/api/v1/dataset/{dataset_id}/task/{task_id}/inspect",
        )
        assert resp.status == 200, await resp.text()
        task_request = await resp.json()
        if task_done(task_request):
            return task_request

        await asyncio.sleep(20)


async def validate_task_output(client: aiohttp.ClientSession, validation: Callable[[BrokerMessage], None]):
    max_retries = 10
    last_retry_exc = None
    for _ in range(max_retries):
        try:
            resp = await client.get("/api/v1/processing/pull", params={"from_cursor": 0, "limit": 1})
            assert resp.status == 200, await resp.text()
            pull_response = await resp.json()
            payloads = pull_response.get("payloads", [])
            assert len(payloads) > 0, "No payload received"
            assert len(payloads) == 1, f"Only one payload expected, got {len(payloads)}"

            message = BrokerMessage()
            message.ParseFromString(base64.b64decode(payloads[0]))
            validation(message)

        except AssertionError as exc:
            last_retry_exc = exc
            await asyncio.sleep(5)
            continue
        else:
            # No exception on the last retry, we're good!
            return

    # if we exceeded retries and we're here, last one failed
    if last_retry_exc is not None:
        pytest.fail(f"Failed to validate task output ater {max_retries}. Last error was: {last_retry_exc!r}")


LABEL_OPERATION_IDENT = "label-operation-ident-1"
LLM_GRAPH_OPERATION_IDENT = "e2e-test-da-graph-agent-1"
TEST_ASK_KEY = "e2e_test_summarized_field_id"


def validate_labeler_output(msg: BrokerMessage):
    assert msg.field_metadata[0].metadata.metadata.classifications[0].labelset == LABEL_OPERATION_IDENT
    assert msg.field_metadata[0].metadata.metadata.classifications[0].label in (
        "TECH",
        "MEDIA",
        "FOOD",
        "HEALTH",
    )


def validate_llm_graph_output(msg: BrokerMessage):
    assert LLM_GRAPH_OPERATION_IDENT in msg.field_metadata[0].metadata.metadata.entities
    assert (
        msg.field_metadata[0].metadata.metadata.entities[LLM_GRAPH_OPERATION_IDENT].entities[0].label
        == "PLAINTIFF"
    )


def validate_prompt_guard_output(msg: BrokerMessage):
    assert len(msg.field_metadata[0].metadata.metadata.classifications) >= 1
    for classification in msg.field_metadata[0].metadata.metadata.classifications:
        assert classification.labelset == "jailbreak_safety"
        assert "JAILBREAK" in classification.label


def validate_prompt_guard_output_text_block(msg: BrokerMessage):
    assert (
        msg.field_metadata[0].metadata.metadata.paragraphs[0].classifications[0].labelset
        == "jailbreak_safety"
    )
    assert msg.field_metadata[0].metadata.metadata.paragraphs[0].classifications[0].label == "JAILBREAK"


def validate_llama_guard_output(msg: BrokerMessage):
    assert len(msg.field_metadata[0].metadata.metadata.classifications) >= 3
    for classification in msg.field_metadata[0].metadata.metadata.classifications:
        assert classification.labelset == "safety"
        assert "unsafe" in classification.label


def validate_llama_guard_output_text_block(msg: BrokerMessage):
    assert msg.field_metadata[0].metadata.metadata.paragraphs[0].classifications[0].labelset == "safety"
    assert "unsafe" in msg.field_metadata[0].metadata.metadata.paragraphs[0].classifications[0].label


def validate_ask_output(msg: BrokerMessage):
    assert len(msg.texts) >= 1
    for key in msg.texts:
        assert TEST_ASK_KEY in key
        assert len(msg.texts[key].body) < 2000


def validate_synthetic_questions_output(msg: BrokerMessage):
    assert msg.question_answers[0].question_answers.question_answers.question_answer[0].question.text != ""
    assert (
        msg.question_answers[0].question_answers.question_answers.question_answer[0].answers[0].reason != ""
    )


def validate_labeler_output_text_block(msg: BrokerMessage):
    assert (
        msg.field_metadata[0].metadata.metadata.paragraphs[0].classifications[0].labelset
        == LABEL_OPERATION_IDENT
    )

    assert msg.field_metadata[0].metadata.metadata.paragraphs[0].classifications[0].label in (
        "TECH",
        "MEDIA",
        "FOOD",
        "HEALTH",
    )


DA_TEST_INPUTS: list[TaskTestInput | ParameterSet] = [
    TaskTestInput(
        filename="financial-news-kb.arrow",
        task_name=TaskName.LABELER,
        parameters=DataAugmentation(
            name="e2e-test-labeler",
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
                        ident=LABEL_OPERATION_IDENT,
                        description="label operation description",
                    )
                )
            ],
            llm=LLMConfig(model="chatgpt-azure-4o-mini"),
        ),
        validate_output=validate_labeler_output,
    ),
    TaskTestInput(
        filename="legal-text-kb.arrow",
        task_name=TaskName.LLM_GRAPH,
        parameters=DataAugmentation(
            name="e2e-test-graph",
            on=ApplyTo.FIELD,
            filter=Filter(),
            operations=[
                Operation(
                    graph=GraphOperation(
                        entity_defs=[
                            EntityDefinition(
                                label="PLAINTIFF",
                                description="The person or entity that initiates a lawsuit",
                            ),
                            EntityDefinition(
                                label="DEFENDANT",
                                description="The person or entity against whom a lawsuit is filed",
                            ),
                            EntityDefinition(
                                label="CONTRACT",
                                description="A legally binding agreement between two or more parties",
                            ),
                            EntityDefinition(
                                label="CLAUSE",
                                description="A specific provision or section of a contract",
                            ),
                            EntityDefinition(label="STATUTE"),
                            EntityDefinition(label="DATE"),
                            EntityDefinition(
                                label="DEFENSE ATTORNEY",
                                description="The lawyer who represents the defendant in a lawsuit",
                            ),
                            EntityDefinition(
                                label="JUDGE",
                                description="The presiding officer in a court of law",
                            ),
                            EntityDefinition(
                                label="PLAINTIFF ATTORNEY",
                                description="The lawyer who represents the plaintiff in a lawsuit",
                            ),
                            EntityDefinition(label="COURT"),
                        ],
                        ident=LLM_GRAPH_OPERATION_IDENT,
                    )
                )
            ],
            llm=LLMConfig(model="gemini-1-5-flash"),
        ),
        validate_output=validate_llm_graph_output,
    ),
    pytest.param(
        TaskTestInput(
            filename="jailbreak-kb.arrow",
            task_name=TaskName.PROMPT_GUARD,
            parameters=DataAugmentation(
                name="e2e-test-prompt-guard",
                on=ApplyTo.FIELD,
                filter=Filter(),
                operations=[Operation(prompt_guard=GuardOperation(enabled=True))],
                llm=LLMConfig(model="chatgpt-azure-4o-mini"),
            ),
            validate_output=validate_prompt_guard_output,
        ),
        marks=pytest.mark.skipif(
            PROMPT_GUARD_DISABLED, reason="Feature flag application_prompt-safety-task is disabled"
        ),
    ),
    pytest.param(
        TaskTestInput(
            filename="toxic-kb.arrow",
            task_name=TaskName.LLAMA_GUARD,
            parameters=DataAugmentation(
                name="e2e-test-llama-guard",
                on=ApplyTo.FIELD,
                filter=Filter(),
                operations=[Operation(llama_guard=GuardOperation(enabled=True))],
                llm=LLMConfig(model="chatgpt-azure-4o-mini"),
            ),
            validate_output=validate_llama_guard_output,
        ),
        marks=pytest.mark.skipif(
            LLAMA_GUARD_DISABLED, reason="Feature flag application_content-safety-task is disabled"
        ),
    ),
    TaskTestInput(
        filename="legal-text-kb.arrow",
        task_name=TaskName.ASK,
        parameters=DataAugmentation(
            name="e2e-test-ask",
            on=ApplyTo.FIELD,
            filter=Filter(),
            operations=[
                Operation(
                    ask=AskOperation(
                        question="Make a short summary of the document",
                        destination=TEST_ASK_KEY,
                        json=False,
                    )
                )
            ],
            llm=LLMConfig(model="chatgpt-azure-4o-mini"),
        ),
        validate_output=validate_ask_output,
    ),
    TaskTestInput(
        filename="legal-text-kb.arrow",
        task_name=TaskName.SYNTHETIC_QUESTIONS,
        parameters=DataAugmentation(
            name="e2e-test-synthetic-questions",
            on=ApplyTo.FIELD,
            filter=Filter(),
            operations=[Operation(qa=QAOperation())],
            llm=LLMConfig(model="chatgpt-azure-4o-mini"),
        ),
        validate_output=validate_synthetic_questions_output,
    ),
    TaskTestInput(
        filename="financial-news-kb.arrow",
        task_name=TaskName.LABELER,
        parameters=DataAugmentation(
            name="e2e-test-labeler-text-block",
            on=ApplyTo.TEXT_BLOCK,
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
                        ident=LABEL_OPERATION_IDENT,
                        description="label operation description",
                    )
                )
            ],
            llm=LLMConfig(model="chatgpt-azure-4o-mini"),
        ),
        validate_output=validate_labeler_output_text_block,
    ),
    pytest.param(
        TaskTestInput(
            filename="jailbreak-kb.arrow",
            task_name=TaskName.PROMPT_GUARD,
            parameters=DataAugmentation(
                name="e2e-test-prompt-guard-text-block",
                on=ApplyTo.TEXT_BLOCK,
                filter=Filter(),
                operations=[Operation(prompt_guard=GuardOperation(enabled=True))],
                llm=LLMConfig(model="chatgpt-azure-4o-mini"),
            ),
            validate_output=validate_prompt_guard_output_text_block,
        ),
        marks=pytest.mark.skipif(
            PROMPT_GUARD_DISABLED, reason="Feature flag application_prompt-safety-task is disabled"
        ),
    ),
    pytest.param(
        TaskTestInput(
            filename="toxic-kb.arrow",
            task_name=TaskName.LLAMA_GUARD,
            parameters=DataAugmentation(
                name="e2e-test-llama-guard-text-block",
                on=ApplyTo.TEXT_BLOCK,
                filter=Filter(),
                operations=[Operation(llama_guard=GuardOperation(enabled=True))],
                llm=LLMConfig(model="chatgpt-azure-4o-mini"),
            ),
            validate_output=validate_llama_guard_output_text_block,
        ),
        marks=pytest.mark.skipif(
            LLAMA_GUARD_DISABLED, reason="Feature flag application_content-safety-task is disabled"
        ),
    ),
]


@pytest.fixture
async def tmp_nua_key(
    nua_client: AsyncNuaClient,
    aiohttp_client,
    regional_api_config,
    global_api_config,
) -> AsyncGenerator[str, None]:
    account_id = global_api_config.permanent_account_id
    pat_client_generator = aiohttp_client(
        base_url=nua_client.url,
        pat_key=global_api_config.permanent_account_owner_pat_token,
        timeout=300,
    )
    pat_client = await pat_client_generator
    nua_client_id, nua_key = await create_nua_key(
        client=pat_client,
        account_id=account_id,
        title=f"E2E DA AGENTS - {nua_client.region}",
    )
    try:
        yield nua_key
    finally:
        await delete_nua_key(client=pat_client, account_id=account_id, nua_client_id=nua_client_id)
        await nua_client.stream_client.aclose()
        await nua_client.client.aclose()


@pytest.mark.asyncio_cooperative
@pytest.mark.parametrize("test_input", DA_TEST_INPUTS, ids=lambda test_input: test_input.parameters.name)
async def test_da_agent_tasks(
    request,
    nua_client: AsyncNuaClient,
    aiohttp_client,
    tmp_nua_key: str,
    test_input: TaskTestInput,
):
    dataset_id = None
    task_id = None
    start_time = asyncio.get_event_loop().time()
    try:
        nua_client_generator = aiohttp_client(base_url=nua_client.url, nua_key=tmp_nua_key, timeout=30)
        client = await nua_client_generator

        dataset_id = await create_dataset(client=client)
        await push_data_to_dataset(client=client, dataset_id=dataset_id, filename=test_input.filename)

        task_id = await start_task(
            client=client,
            dataset_id=dataset_id,
            task_name=test_input.task_name,
            parameters=test_input.parameters,
        )
        print(f"{request.node.name} ::  task_id: {task_id}")
        task_request = await wait_for_task_completion(client=client, dataset_id=dataset_id, task_id=task_id)
        assert task_request["completed"] is True
        assert task_request["failed"] is False

        await validate_task_output(
            client=client,
            validation=test_input.validate_output,
        )
    finally:
        if dataset_id is not None:
            if task_id is not None:
                await stop_task(client=client, dataset_id=dataset_id, task_id=task_id)
                await delete_task(client=client, dataset_id=dataset_id, task_id=task_id)
            await delete_dataset(client=client, dataset_id=dataset_id)
        end_time = asyncio.get_event_loop().time()
        elapsed_time = end_time - start_time
        print(f"{request.node.name} :: Task completed in {elapsed_time:.2f} seconds.")
