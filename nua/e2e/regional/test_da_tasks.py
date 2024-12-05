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

from dataclasses import dataclass


@dataclass
class TestInput:
    filename: str
    task_name: TaskName
    parameters: PARAMETERS_TYPING


@pytest.fixture
def httpx_client() -> Callable[[str, str], AsyncGenerator[AsyncClient, None]]:
    async def create_httpx_client(
        base_url: str, nua_key: str
    ) -> AsyncGenerator[AsyncClient, None]:
        client = AsyncClient()
        async with AsyncClient(
            base_url=base_url, headers={"X-NUCLIA-NUAKEY": f"Bearer {nua_key}"}
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
    assert resp.status_code == 201
    return resp.json()["id"]


async def push_data_to_dataset(client: AsyncClient, dataset_id: str, filename: str):
    async with aiofiles.open(define_path(filename), "rb") as f:
        content = await f.read()
    resp = await client.put(
        f"/api/v1/dataset/{dataset_id}/partition/0",
        data=content,
    )
    assert resp.status_code == 204


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
    assert resp.status_code == 200
    return resp.json()["id"]


async def wait_for_task_completion(
    client: AsyncClient,
    dataset_id: str,
    task_id: str,
    max_duration: int = 600,
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
        assert resp.status_code == 200
        task_request = resp.json()

        if task_done(task_request):
            return task_request

        await asyncio.sleep(20)


async def check_output(client: AsyncClient):
    resp = await client.get("/api/v1/processing/pull")
    assert resp.status_code == 200
    pull_response = resp.json()
    print(pull_response)  # TODO: remove
    # TODO: Add checks for pull_response attributes


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
                                label="Science",
                                description="Content related to science",
                            ),
                        ],
                        ident="label-operation-ident-1",
                        description="label operation description",
                    )
                )
            ],
            llm=LLMConfig(model="chatgpt-azure-4o-mini"),
        ),
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
                                label="Developer",
                                description="Person that implements software solutions",
                            ),
                            EntityDefinition(
                                label="CTO",
                                description=(
                                    "The highest technology executive position "
                                    "within a company and leads the technology or engineering department"
                                ),
                            ),
                        ],
                        ident="e2e-test-da-graph-agent-1",
                    )
                )
            ],
            llm=LLMConfig(model="chatgpt-azure-4o-mini"),
        ),
    ),
    # TestInput(
    #     filename="legal-text-kb.arrow",  # TODO: change
    #     task_name=TaskName.PROMPT_GUARD,
    #     parameters=DataAugmentation(
    #         name="e2e-test-prompt-guard",
    #         on=ApplyTo.FIELD,
    #         filter=Filter(),
    #         operations=[Operation(prompt_guard=GuardOperation(enable=True))],
    #         llm=LLMConfig(model="chatgpt-azure-4o-mini"),
    #     ),
    # ),
    # TestInput(
    #     filename="legal-text-kb.arrow",  # TODO: change
    #     task_name=TaskName.LLAMA_GUARD,
    #     parameters=DataAugmentation(
    #         name="e2e-test-llama-guard",
    #         on=ApplyTo.FIELD,
    #         filter=Filter(),
    #         operations=[Operation(llama_guard=GuardOperation(enable=True))],
    #         llm=LLMConfig(model="chatgpt-azure-4o-mini"),
    #     ),
    # ),
    TestInput(
        filename="legal-text-kb.arrow",  # TODO: change
        task_name=TaskName.ASK,
        parameters=DataAugmentation(
            name="e2e-test-ask",
            on=ApplyTo.FIELD,
            filter=Filter(),
            operations=[
                Operation(
                    ask=AskOperation(
                        question="Make a short summary of the document",
                        destination="e2e_test_summarized_field_id",
                        json=False,
                    )
                )
            ],
            llm=LLMConfig(model="chatgpt-azure-4o-mini"),
        ),
    ),
    TestInput(
        filename="legal-text-kb.arrow",  # TODO: change
        task_name=TaskName.SYNTHETIC_QUESTIONS,
        parameters=DataAugmentation(
            name="e2e-test-synthetic-questions",
            on=ApplyTo.FIELD,
            filter=Filter(),
            operations=[Operation(qa=QAOperation())],
            llm=LLMConfig(model="chatgpt-azure-4o-mini"),
        ),
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("test_input", DA_TEST_INPUTS)
async def test_da_agent_tasks(
    nua_config: str,
    httpx_client: AsyncGenerator[AsyncClient, None],
    test_input: TestInput,
):
    client_generator = httpx_client(
        base_url=f"https://{nua_config}", nua_key=TOKENS[nua_config]
    )
    client = await anext(client_generator)

    dataset_id = await create_dataset(client=client)
    await push_data_to_dataset(
        client=client, dataset_id=dataset_id, filename=test_input.filename
    )

    task_id = await start_task(
        client=client,
        dataset_id=dataset_id,
        task_name=test_input.task_name,
        parameters=test_input.parameters,
    )
    print(f"task_id: {task_id}")  # TODO: remove
    task_request = await wait_for_task_completion(
        client=client, dataset_id=dataset_id, task_id=task_id
    )
    assert task_request["completed"] is True
    assert task_request["failed"] is False

    await check_output(client=client)

    # TODO: delete tasks and dataset even if assert fails
