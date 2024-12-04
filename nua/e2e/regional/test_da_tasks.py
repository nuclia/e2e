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
)
from conftest import TOKENS
import time
from regional.utils import define_path
from typing import Callable, Generator
from httpx import Client


@pytest.fixture
def httpx_client() -> Callable[[str, str], Generator[Client, None, None]]:
    def create_httpx_client(
        base_url: str, nua_key: str
    ) -> Generator[Client, None, None]:
        client = Client()
        with Client() as client:
            client.base_url = base_url
            client.headers.update({"X-NUCLIA-NUAKEY": f"Bearer {nua_key}"})
            yield client

    return create_httpx_client


def task_done(task_request: dict) -> bool:
    return task_request["failed"] or task_request["completed"]


def create_dataset(client: Client) -> str:
    dataset_body = {
        "name": "e2e-test-dataset",
        "filter": {"labels": []},
        "type": "FIELD_CLASSIFICATION",
    }
    resp = client.post("/api/v1/datasets", json=dataset_body)
    assert resp.status_code == 201
    return resp.json()["id"]


def push_data_to_dataset(client: Client, dataset_id: str):
    with open(define_path("field_classification.arrow"), "rb") as f:
        content = f.read()
    resp = client.put(
        f"/api/v1/dataset/{dataset_id}/partition/0",
        data=content,
    )
    assert resp.status_code == 204


def start_task(
    client: Client,
    dataset_id: str,
    task_name: str,
    parameters: PARAMETERS_TYPING,
) -> str:
    resp = client.post(
        f"/api/v1/dataset/{dataset_id}/task/start",
        json=TaskStart(name=task_name, parameters=parameters).model_dump(),
    )
    assert resp.status_code == 200
    return resp.json()["id"]


def wait_for_task_completion(
    client: Client,
    dataset_id: str,
    task_id: str,
    max_duration: int = 300,
):
    start_time = time.time()
    while True:
        elapsed_time = time.time() - start_time
        if elapsed_time > max_duration:
            raise TimeoutError(
                f"Task {task_id} did not complete within the maximum allowed time of {max_duration} seconds."
            )

        resp = client.get(
            f"/api/v1/dataset/{dataset_id}/task/{task_id}/inspect",
        )
        assert resp.status_code == 200
        task_request = resp.json()
        print(task_request)  # TODO: remove
        if task_done(task_request):
            return task_request

        time.sleep(20)


def check_output(client: Client):
    resp = client.get("/api/v1/processing/pull")
    assert resp.status_code == 200
    pull_response = resp.json()
    # TODO: Add checks for pull_response attributes


@pytest.mark.timeout(360)
def test_da_labeler(nua_config, httpx_client):
    client_generator = httpx_client(
        base_url=f"https://{nua_config}", nua_key=TOKENS[nua_config]
    )
    client = next(client_generator)

    dataset_id = create_dataset(client=client)
    push_data_to_dataset(client=client, dataset_id=dataset_id)

    parameters = DataAugmentation(
        name="e2e-test-labeler",
        on=ApplyTo.FIELD,
        filter=Filter(),
        operations=[
            Operation(
                label=LabelOperation(
                    labels=[
                        Label(label="Science", description="Content related to science")
                    ]
                )
            )
        ],
        llm=LLMConfig(model="chatgpt-azure-4o-mini"),
    )
    task_id = start_task(
        client=client,
        dataset_id=dataset_id,
        task_name=TaskName.LABELER,
        parameters=parameters,
    )

    task_request = wait_for_task_completion(
        client=client, dataset_id=dataset_id, task_id=task_id
    )
    assert task_request["completed"] is True
    assert task_request["failed"] is False

    check_output(client=client)


@pytest.mark.timeout(360)
def test_da_graph(nua_config, httpx_client):
    client_generator = httpx_client(
        base_url=f"https://{nua_config}", nua_key=TOKENS[nua_config]
    )
    client = next(client_generator)

    dataset_id = create_dataset(client=client)
    push_data_to_dataset(client=client, dataset_id=dataset_id)

    parameters = DataAugmentation(
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
    )
    task_id = start_task(
        client=client,
        dataset_id=dataset_id,
        task_name=TaskName.LLM_GRAPH,
        parameters=parameters,
    )

    task_request = wait_for_task_completion(
        client=client, dataset_id=dataset_id, task_id=task_id
    )
    assert task_request["completed"] is True
    assert task_request["failed"] is False

    check_output(client=client)
