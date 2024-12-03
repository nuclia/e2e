from pathlib import Path

import pytest
from nuclia_models.worker.tasks import (
    TaskName,
    DataAugmentation,
    TaskStart,
)
from nuclia_models.worker.proto import (
    ApplyTo,
    Filter,
    LLMConfig,
    Operation,
    LabelOperation,
    Label,
)
import requests
from conftest import TOKENS
import time

FILE_PATH = f"{Path(__file__).parent.parent}/assets/"


def define_path(file: str):
    return FILE_PATH + file


def task_done(task_request: dict) -> bool:
    return task_request["failed"] or task_request["completed"]


@pytest.mark.timeout(360)
def test_da_labeler(nua_config):
    path = define_path("field_classification.arrow")

    base_url = f"https://{nua_config}"
    nua_key = TOKENS[nua_config]
    headers = {"X-NUCLIA-NUAKEY": f"Bearer {nua_key}"}

    # step 1, create a dataset
    dataset_body = {
        "name": "e2e-test-dataset",
        "filter": {"labels": []},
        "type": "FIELD_CLASSIFICATION",
    }
    resp = requests.post(
        f"{base_url}/api/v1/datasets", headers=headers, json=dataset_body
    )
    assert resp.status_code == 201
    dataset_id = resp.json()["id"]

    # step 2, push data to the dataset
    with open(path, "rb") as f:
        content = f.read()

    resp = requests.put(
        f"{base_url}/api/v1/dataset/{dataset_id}/partition/0",
        headers=headers,
        data=content,
    )
    assert resp.status_code == 204

    # step 3, create an agent for a dataset
    resp = requests.post(
        f"{base_url}/api/v1/dataset/{dataset_id}/task/start",
        headers=headers,
        json=TaskStart(
            name=TaskName.LABELER,
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
                                )
                            ]
                        )
                    )
                ],
                llm=LLMConfig(model="chatgpt-azure-4o-mini"),
            ),
        ).model_dump(),
    )
    assert resp.status_code == 200
    task_id = resp.json()["id"]

    # step 4, wait till the task is completed
    start_time = time.time()
    max_duration = 5 * 60  # 5 minutes

    task_request = None
    while True:
        elapsed_time = time.time() - start_time
        if elapsed_time > max_duration:
            raise TimeoutError(
                "Task {task_id} did not complete within the maximum allowed time of {max_duration} seconds."
            )

        resp = requests.get(
            f"{base_url}/api/v1/dataset/{dataset_id}/task/{task_id}/inspect",
            headers=headers,
        )
        assert resp.status_code == 200
        task_request = resp.json()

        if task_done(task_request):
            break

        # Wait for 20 seconds before the next request
        time.sleep(20)

    assert task_request is not None
    assert task_request["completed"] is True
    assert task_request["failed"] is False

    # step 5, check the output result
    resp = requests.get(f"{base_url}/api/v1/processing/pull", headers=headers)
    assert resp.status_code == 200
    pull_response = resp.json()
    # TODO: check attributes pull response
