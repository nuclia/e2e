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


@dataclass
class TestInput:
    filename: str
    task_name: TaskName
    parameters: PARAMETERS_TYPING
    validate_output: Callable[[BrokerMessage], None]


@pytest.fixture
def httpx_client() -> Callable[[str, str], AsyncGenerator[AsyncClient, None]]:
    async def create_httpx_client(
        base_url: str, nua_key: str
    ) -> AsyncGenerator[AsyncClient, None]:
        client = AsyncClient()
        async with AsyncClient(
            base_url=base_url,
            headers={"X-NUCLIA-NUAKEY": f"Bearer {nua_key}"},
            timeout=30,
        ) as client:
            yield client

    return create_httpx_client


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


async def delete_task(client: AsyncClient, dataset_id: str, task_id: str):
    resp = await client.delete(f"/api/v1/dataset/{dataset_id}/task/{task_id}")
    assert resp.status_code == 200, resp.text


async def wait_for_task_completion(
    client: AsyncClient,
    dataset_id: str,
    task_id: str,
    max_duration: int = 1200,
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


async def get_last_message_id(client: AsyncClient) -> int:
    max_retries = 20
    for _ in range(max_retries):
        resp = await client.get(
            "/api/v1/processing/pull",
            params={
                "from_cursor": 0,
                "limit": 999999,  # TODO: refactor, this is not scalable
            },
        )
        assert resp.status_code == 200, resp.text
        pull_response = resp.json()
        cursor = pull_response["cursor"]
        if cursor is not None:
            return cursor
        await asyncio.sleep(5)

    raise ValueError(f"Failed to retrieve a valid cursor after {max_retries} attempts")


async def validate_task_output(
    client: AsyncClient, from_cursor: int, validation: Callable[[BrokerMessage], None]
):
    max_retries = 20
    for _ in range(max_retries):
        resp = await client.get(
            "/api/v1/processing/pull", params={"from_cursor": from_cursor, "limit": 1}
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
    assert msg.field_metadata[0].metadata.metadata.classifications[0].label == "TECH"


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
    pass


def validate_llama_guard_output(msg: BrokerMessage):
    assert len(msg.field_metadata[0].metadata.metadata.classifications) == 4
    for classification in msg.field_metadata[0].metadata.metadata.classifications:
        assert classification.labelset == "safety"
        assert "unsafe" in classification.label


def validate_ask_output(msg: BrokerMessage):
    assert len(msg.texts) == 2
    for key in msg.texts:
        assert TEST_ASK_KEY in key
        assert len(msg.texts[key].body) < 2000


def validate_synthetic_questions_output(msg: BrokerMessage):
    assert (
        "legal"
        in msg.question_answers[0]
        .question_answers.question_answers.question_answer[0]
        .question.text
    )
    assert (
        "legal"
        in msg.question_answers[0]
        .question_answers.question_answers.question_answer[0]
        .answers[0]
        .reason
    )


def validate_labeler_output_text_block(msg: BrokerMessage):
    assert (
        msg.field_metadata[0]
        .metadata.metadata.paragraphs[0]
        .classifications[0]
        .labelset
        == LABEL_OPERATION_IDENT
    )

    assert (
        msg.field_metadata[0].metadata.metadata.paragraphs[0].classifications[0].label
        == "TECH"
    )


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
    # TestInput(
    #     filename="legal-text-kb.arrow",
    #     task_name=TaskName.PROMPT_GUARD,
    #     parameters=DataAugmentation(
    #         name="e2e-test-prompt-guard",
    #         on=ApplyTo.FIELD,
    #         filter=Filter(),
    #         operations=[Operation(prompt_guard=GuardOperation(enable=True))],
    #         llm=LLMConfig(model="chatgpt-azure-4o-mini"),
    #     ),
    #     validate_output=validate_prompt_guard_output,
    # ),
    TestInput(
        filename="legal-text-kb.arrow",
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
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "test_input", DA_TEST_INPUTS, ids=lambda test_input: test_input.parameters.name
)
async def test_da_agent_tasks(
    nua_config: str,
    httpx_client: AsyncGenerator[AsyncClient, None],
    test_input: TestInput,
):
    client_generator = httpx_client(
        base_url=f"https://{nua_config}", nua_key=TOKENS[nua_config]
    )
    client = await anext(client_generator)

    last_msg_id = await get_last_message_id(client=client)

    dataset_id = None
    task_id = None
    try:
        dataset_id = await create_dataset(client=client)
        print(f"dataset_id: {dataset_id}")
        await push_data_to_dataset(
            client=client, dataset_id=dataset_id, filename=test_input.filename
        )

        task_id = await start_task(
            client=client,
            dataset_id=dataset_id,
            task_name=test_input.task_name,
            parameters=test_input.parameters,
        )
        print(f"task_id: {task_id}")
        task_request = await wait_for_task_completion(
            client=client, dataset_id=dataset_id, task_id=task_id
        )
        assert task_request["completed"] is True
        assert task_request["failed"] is False

        await validate_task_output(
            client=client,
            from_cursor=last_msg_id,
            validation=test_input.validate_output,
        )
    finally:
        if dataset_id is not None:
            if task_id is not None:
                await delete_task(client=client, dataset_id=dataset_id, task_id=task_id)
            await delete_dataset(client=client, dataset_id=dataset_id)
