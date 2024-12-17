import pytest
from nuclia_models.worker.tasks import (
    TaskName,
    DataAugmentation,
    TaskStart,
    PARAMETERS_TYPING,
)
from nuclia_models.worker.proto import (
    ApplyTo,
    Filter,
    LLMConfig,
    Operation,
    LabelOperation,
    Label,
    GraphOperation,
    EntityDefinition,
    GuardOperation,
    AskOperation,
    QAOperation,
)
from conftest import TOKENS
from regional.utils import define_path
from typing import Callable, AsyncGenerator
from httpx import AsyncClient
import asyncio
import aiofiles
from nucliadb_protos.writer_pb2 import BrokerMessage
from dataclasses import dataclass
import base64
from typing import Optional


@dataclass
class TestInput:
    filename: str
    task_name: TaskName
    parameters: PARAMETERS_TYPING
    validate_output: Callable[[BrokerMessage], None]


@pytest.fixture
def httpx_client() -> Callable[[str, str], AsyncGenerator[AsyncClient, None]]:
    async def create_httpx_client(
        base_url: str,
        nua_key: Optional[str] = None,
        pat_key: Optional[str] = None,
        timeout: int = 5,
    ) -> AsyncGenerator[AsyncClient, None]:
        client = AsyncClient()
        async with AsyncClient(
            base_url=base_url,
            headers={"X-NUCLIA-NUAKEY": f"Bearer {nua_key}"}
            if nua_key
            else {"Authorization": f"Bearer {pat_key}"},
            timeout=timeout,
        ) as client:
            yield client

    return create_httpx_client


async def create_nua_key(
    client: AsyncClient, account_id: str, title: str
) -> tuple[str, str]:
    body = {
        "title": title,
        "contact": "temporal key, safe to delete",
    }
    resp = await client.post(f"/api/v1/account/{account_id}/nua_clients", json=body)
    assert resp.status_code == 201, resp.text
    nua_response = resp.json()
    return nua_response["client_id"], nua_response["token"]


async def delete_nua_key(client: AsyncClient, account_id: str, nua_client_id: str):
    resp = await client.delete(
        f"/api/v1/account/{account_id}/nua_client/{nua_client_id}"
    )
    assert resp.status_code == 204, resp.text


def task_done(task_request: dict) -> bool:
    return task_request["failed"] or task_request["completed"]


async def create_dataset(client: AsyncClient) -> str:
    dataset_body = {
        "name": "e2e-test-dataset",
        "filter": {"labels": []},
        "type": "FIELD_STREAMING",
    }
    resp = await client.post("/api/v1/datasets", json=dataset_body)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def delete_dataset(client: AsyncClient, dataset_id: str):
    resp = await client.delete(f"/api/v1/dataset/{dataset_id}")
    assert resp.status_code == 204, resp.text


async def push_data_to_dataset(client: AsyncClient, dataset_id: str, filename: str):
    async with aiofiles.open(define_path(filename), "rb") as f:
        content = await f.read()
    resp = await client.put(
        f"/api/v1/dataset/{dataset_id}/partition/1",
        data=content,
    )
    assert resp.status_code == 204, resp.text


async def start_task(
    client: AsyncClient,
    dataset_id: str,
    task_name: str,
    parameters: PARAMETERS_TYPING,
) -> str:
    resp = await client.post(
        f"/api/v1/dataset/{dataset_id}/task/start",
        json=TaskStart(name=task_name, parameters=parameters).model_dump(),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def stop_task(client: AsyncClient, dataset_id: str, task_id: str):
    resp = await client.post(f"/api/v1/dataset/{dataset_id}/task/{task_id}/stop")
    assert resp.status_code == 200, resp.text


async def delete_task(client: AsyncClient, dataset_id: str, task_id: str):
    resp = await client.delete(f"/api/v1/dataset/{dataset_id}/task/{task_id}")
    assert resp.status_code == 200, resp.text


async def wait_for_task_completion(
    client: AsyncClient,
    dataset_id: str,
    task_id: str,
    max_duration: int = 2300,
):
    start_time = asyncio.get_event_loop().time()
    while True:
        elapsed_time = asyncio.get_event_loop().time() - start_time
        if elapsed_time > max_duration:
            raise TimeoutError(
                f"Task {task_id} did not complete within the maximum allowed time of {max_duration} seconds."
            )

        resp = await client.get(
            f"/api/v1/dataset/{dataset_id}/task/{task_id}/inspect",
        )
        assert resp.status_code == 200, resp.text
        task_request = resp.json()
        if task_done(task_request):
            return task_request

        await asyncio.sleep(20)


async def validate_task_output(
    client: AsyncClient, validation: Callable[[BrokerMessage], None]
):
    max_retries = 5
    for _ in range(max_retries):
        resp = await client.get(
            "/api/v1/processing/pull", params={"from_cursor": 0, "limit": 1}
        )
        assert resp.status_code == 200, resp.text
        pull_response = resp.json()
        if pull_response["payloads"]:
            assert len(pull_response["payloads"]) == 1
            message = BrokerMessage()
            message.ParseFromString(base64.b64decode(pull_response["payloads"][0]))
            validation(message)
            return
        await asyncio.sleep(5)
    raise ValueError(f"Failed to retrieve a task output after {max_retries} attempts")


LABEL_OPERATION_IDENT = "label-operation-ident-1"
LLM_GRAPH_OPERATION_IDENT = "e2e-test-da-graph-agent-1"
TEST_ASK_KEY = "e2e_test_summarized_field_id"


def validate_labeler_output(msg: BrokerMessage):
    assert (
        msg.field_metadata[0].metadata.metadata.classifications[0].labelset
        == LABEL_OPERATION_IDENT
    )
    assert msg.field_metadata[0].metadata.metadata.classifications[0].label in (
        "TECH",
        "MEDIA",
        "FOOD",
        "HEALTH",
    )


def validate_llm_graph_output(msg: BrokerMessage):
    assert LLM_GRAPH_OPERATION_IDENT in msg.field_metadata[0].metadata.metadata.entities
    assert (
        msg.field_metadata[0]
        .metadata.metadata.entities[LLM_GRAPH_OPERATION_IDENT]
        .entities[0]
        .label
        == "PLAINTIFF"
    )


def validate_prompt_guard_output(msg: BrokerMessage):
    assert len(msg.field_metadata[0].metadata.metadata.classifications) >= 1
    for classification in msg.field_metadata[0].metadata.metadata.classifications:
        assert classification.labelset == "jailbreak_safety"
        assert "JAILBREAK" in classification.label


def validate_prompt_guard_output_text_block(msg: BrokerMessage):
    assert (
        msg.field_metadata[0]
        .metadata.metadata.paragraphs[0]
        .classifications[0]
        .labelset
        == "jailbreak_safety"
    )
    assert (
        msg.field_metadata[0].metadata.metadata.paragraphs[0].classifications[0].label
        == "JAILBREAK"
    )


def validate_llama_guard_output(msg: BrokerMessage):
    assert len(msg.field_metadata[0].metadata.metadata.classifications) >= 3
    for classification in msg.field_metadata[0].metadata.metadata.classifications:
        assert classification.labelset == "safety"
        assert "unsafe" in classification.label


def validate_llama_guard_output_text_block(msg: BrokerMessage):
    assert (
        msg.field_metadata[0]
        .metadata.metadata.paragraphs[0]
        .classifications[0]
        .labelset
        == "safety"
    )
    assert (
        "unsafe"
        in msg.field_metadata[0]
        .metadata.metadata.paragraphs[0]
        .classifications[0]
        .label
    )


def validate_ask_output(msg: BrokerMessage):
    assert len(msg.texts) >= 1
    for key in msg.texts:
        assert TEST_ASK_KEY in key
        assert len(msg.texts[key].body) < 2000


def validate_synthetic_questions_output(msg: BrokerMessage):
    assert (
        msg.question_answers[0]
        .question_answers.question_answers.question_answer[0]
        .question.text
        != ""
    )
    assert (
        msg.question_answers[0]
        .question_answers.question_answers.question_answer[0]
        .answers[0]
        .reason
        != ""
    )


def validate_labeler_output_text_block(msg: BrokerMessage):
    assert (
        msg.field_metadata[0]
        .metadata.metadata.paragraphs[0]
        .classifications[0]
        .labelset
        == LABEL_OPERATION_IDENT
    )

    assert msg.field_metadata[0].metadata.metadata.paragraphs[0].classifications[
        0
    ].label in ("TECH", "MEDIA", "FOOD", "HEALTH")


DA_TEST_INPUTS: list[TestInput] = [
    TestInput(
        filename="financial-new-kb.arrow",
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
    TestInput(
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
            llm=LLMConfig(model="chatgpt-azure-4o-mini"),
        ),
        validate_output=validate_llm_graph_output,
    ),
    TestInput(
        filename="jailbreak-kb.arrow",
        task_name=TaskName.PROMPT_GUARD,
        parameters=DataAugmentation(
            name="e2e-test-prompt-guard",
            on=ApplyTo.FIELD,
            filter=Filter(),
            operations=[Operation(prompt_guard=GuardOperation(enable=True))],
            llm=LLMConfig(model="chatgpt-azure-4o-mini"),
        ),
        validate_output=validate_prompt_guard_output,
    ),
    TestInput(
        filename="toxic-kb.arrow",
        task_name=TaskName.LLAMA_GUARD,
        parameters=DataAugmentation(
            name="e2e-test-llama-guard",
            on=ApplyTo.FIELD,
            filter=Filter(),
            operations=[Operation(llama_guard=GuardOperation(enable=True))],
            llm=LLMConfig(model="chatgpt-azure-4o-mini"),
        ),
        validate_output=validate_llama_guard_output,
    ),
    TestInput(
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
    TestInput(
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
    TestInput(
        filename="financial-new-kb.arrow",
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
    TestInput(
        filename="jailbreak-kb.arrow",
        task_name=TaskName.PROMPT_GUARD,
        parameters=DataAugmentation(
            name="e2e-test-prompt-guard-text-block",
            on=ApplyTo.TEXT_BLOCK,
            filter=Filter(),
            operations=[Operation(prompt_guard=GuardOperation(enable=True))],
            llm=LLMConfig(model="chatgpt-azure-4o-mini"),
        ),
        validate_output=validate_prompt_guard_output_text_block,
    ),
    TestInput(
        filename="toxic-kb.arrow",
        task_name=TaskName.LLAMA_GUARD,
        parameters=DataAugmentation(
            name="e2e-test-llama-guard-text-block",
            on=ApplyTo.TEXT_BLOCK,
            filter=Filter(),
            operations=[Operation(llama_guard=GuardOperation(enable=True))],
            llm=LLMConfig(model="chatgpt-azure-4o-mini"),
        ),
        validate_output=validate_llama_guard_output_text_block,
    ),
]


@pytest.fixture
async def tmp_nua_key(
    nua_config: str, httpx_client: AsyncGenerator[AsyncClient, None]
) -> AsyncGenerator[str, None]:
    account_id = TOKENS[nua_config].account_id
    pat_client_generator = httpx_client(
        base_url=f"https://{nua_config}", pat_key=TOKENS[nua_config].pat_key, timeout=30
    )
    pat_client = await anext(pat_client_generator)
    nua_client_id, nua_key = await create_nua_key(
        client=pat_client,
        account_id=account_id,
        title=f"E2E DA AGENTS - {nua_config}",
    )
    try:
        yield nua_key
    finally:
        await delete_nua_key(
            client=pat_client, account_id=account_id, nua_client_id=nua_client_id
        )


@pytest.mark.asyncio_cooperative
@pytest.mark.parametrize(
    "test_input", DA_TEST_INPUTS, ids=lambda test_input: test_input.parameters.name
)
async def test_da_agent_tasks(
    nua_config: str,
    httpx_client: AsyncGenerator[AsyncClient, None],
    tmp_nua_key,
    test_input: TestInput,
):
    dataset_id = None
    task_id = None
    start_time = asyncio.get_event_loop().time()
    try:
        nua_client_generator = httpx_client(
            base_url=f"https://{nua_config}", nua_key=tmp_nua_key, timeout=30
        )
        nua_client = await anext(nua_client_generator)

        dataset_id = await create_dataset(client=nua_client)
        await push_data_to_dataset(
            client=nua_client, dataset_id=dataset_id, filename=test_input.filename
        )

        task_id = await start_task(
            client=nua_client,
            dataset_id=dataset_id,
            task_name=test_input.task_name,
            parameters=test_input.parameters,
        )
        print(f"{test_input.parameters.name} task_id: {task_id}")
        task_request = await wait_for_task_completion(
            client=nua_client, dataset_id=dataset_id, task_id=task_id
        )
        assert task_request["completed"] is True
        assert task_request["failed"] is False

        await validate_task_output(
            client=nua_client,
            validation=test_input.validate_output,
        )
    finally:
        if dataset_id is not None:
            if task_id is not None:
                await stop_task(
                    client=nua_client, dataset_id=dataset_id, task_id=task_id
                )
                await delete_task(
                    client=nua_client, dataset_id=dataset_id, task_id=task_id
                )
            await delete_dataset(client=nua_client, dataset_id=dataset_id)
        end_time = asyncio.get_event_loop().time()
        elapsed_time = end_time - start_time
        print(
            f"Test {test_input.parameters.name} completed in {elapsed_time:.2f} seconds."
        )
