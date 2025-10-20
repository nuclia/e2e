from collections.abc import AsyncIterator
from nuclia import get_regional_url
from nuclia import sdk
from nuclia.lib.kb import AsyncNucliaDBClient
from nuclia.sdk.auth import AsyncNucliaAuth
from nuclia_e2e.utils import get_async_kb_ndb_client
from nuclia_models.worker.proto import ApplyTo
from nuclia_models.worker.proto import AskOperation
from nuclia_models.worker.proto import Filter
from nuclia_models.worker.proto import LLMConfig
from nuclia_models.worker.proto import Operation
from nuclia_models.worker.tasks import ApplyOptions
from nuclia_models.worker.tasks import DataAugmentation
from nuclia_models.worker.tasks import TaskName
from nuclia_models.worker.tasks import TaskResponse
from nucliadb_models import TextField
from nucliadb_sdk.v2.exceptions import NotFoundError
from pytest_asyncio_cooperative import Lock  # type: ignore[import-untyped]

import asyncio
import contextlib
import os
import time
import traceback

locks: dict[str, Lock] = {}


@contextlib.asynccontextmanager
async def lock(key: str) -> AsyncIterator[Lock]:
    _lock = locks.setdefault(key, Lock())
    async with _lock():
        yield


async def root_request(
    auth: AsyncNucliaAuth,
    method: str,
    path: str,
    data: dict | None = None,
    headers: dict | None = None,
) -> dict | None:
    """
    Make a request to the API with root credentials. This is not currently supported by the SDK,
    so we need to do it manually.
    """
    headers = headers or {}
    stage_root_pat_token = os.environ["STAGE_ROOT_PAT_TOKEN"]
    headers["Authorization"] = f"Bearer {stage_root_pat_token}"
    resp = await auth.client.request(
        method,
        path,
        json=data,
        headers=headers,
    )
    resp.raise_for_status()
    if resp.status_code == 204:
        return None
    return resp.json()


@contextlib.asynccontextmanager
async def as_default_generative_model_for_kb(
    kb_id: str, zone: str, auth: AsyncNucliaAuth, generative_model: str
) -> AsyncIterator[None]:
    """
    Context manager that sets the KB's default generative model and restores the previous one upon exit.
    """
    # A lock is needed because some tests are reusing the same kb and changing the learning config.
    # As we are running the tests concurrently, otherwise they mess up each other.
    async with lock(f"learning-config-{kb_id}"):
        ndb = get_async_kb_ndb_client(zone=zone, kbid=kb_id, user_token=auth._config.token)
        kb = sdk.AsyncNucliaKB()
        previous = await kb.get_configuration(ndb=ndb)
        previous_generative_model = previous["generative_model"]
        await kb.update_configuration(ndb=ndb, generative_model=generative_model)
        try:
            yield
        finally:
            await kb.update_configuration(ndb=ndb, generative_model=previous_generative_model)


async def has_generated_field(
    ndb: AsyncNucliaDBClient,
    kb: sdk.AsyncNucliaKB,
    resource_slug: str,
    expected_field_id_prefix: str,
) -> bool:
    """
    Check if the resource has the extracted text for the generated field.
    """
    try:
        res = await kb.resource.get(slug=resource_slug, show=["values", "extracted"], ndb=ndb)
    except NotFoundError:
        # some resource may still be missing from nucliadb, let's wait more
        return False
    try:
        for fid, data in res.data.texts.items():
            if fid.startswith(expected_field_id_prefix) and data.extracted.text.text is not None:
                return True
    except (TypeError, AttributeError):
        # If the resource does not have the expected structure, let's wait more
        return False
    else:
        # If we reach here, it means the field was not found
        return False


async def create_omelette_resource(ndb: AsyncNucliaDBClient):
    kb = sdk.AsyncNucliaKB()
    slug = "omelette"
    await kb.resource.create(
        ndb=ndb,
        slug=slug,
        texts={"omelette": TextField(body="To cook an omelette, you need to crack the egg.")},
    )
    max_wait_seconds: int = 300
    start = time.time()
    processed = False
    while (time.time() - start) < max_wait_seconds:
        resource = await kb.resource.get(slug=slug, show=["values"])
        status = resource.data.texts["omelette"].status
        if status == "PROCESSED":
            processed = True
            break
        print(status)
        await asyncio.sleep(5)
    assert processed, "Resource not processed in time"


async def create_ask_agent(
    kb_id: str,
    zone: str,
    auth: AsyncNucliaAuth,
    da_name: str,
    question: str,
    generative_model: str,
    generative_model_provider: str,
    destination_field_prefix: str,
) -> str:
    ndb = get_async_kb_ndb_client(zone=zone, kbid=kb_id, user_token=auth._config.token)
    kb = sdk.AsyncNucliaKB()
    tr: TaskResponse = await kb.task.start(
        ndb=ndb,
        task_name=TaskName.ASK,
        apply=ApplyOptions.NEW,
        parameters=DataAugmentation(
            name=da_name,
            on=ApplyTo.FIELD,
            filter=Filter(),
            operations=[
                Operation(
                    ask=AskOperation(
                        question=question,
                        destination=destination_field_prefix,
                    )
                )
            ],
            llm=LLMConfig(model=generative_model, provider=generative_model_provider),
        ),
    )
    task_id = tr.id
    return task_id


async def clean_ask_test_tasks(kb: sdk.AsyncNucliaKB, ndb: AsyncNucliaDBClient, to_delete: list[str]):
    tasks = await kb.task.list(ndb=ndb)
    for task in tasks.running + tasks.done + tasks.configs:
        if task.id in to_delete:
            try:
                await kb.task.delete(ndb=ndb, task_id=task.id, cleanup=True)
            except Exception as ex:
                print(f"Error deleting task {task.id}: {ex}")
                traceback.print_exc()


class CustomModels:
    def __init__(
        self,
        auth: AsyncNucliaAuth,
        zone: str,
        account_id: str,
    ):
        self.auth = auth
        self.zone = zone
        self.account_id = account_id

    async def add(
        self,
        model_data: dict,
        kbs: list[str],
    ):
        # Add model to the account
        path = get_regional_url(self.zone, f"/api/v1/account/{self.account_id}/models")
        response = await root_request(self.auth, "POST", path, data=model_data)
        assert response is not None
        model_id = response["id"]

        # Add model to the kbs
        for kb in kbs:
            path = get_regional_url(self.zone, f"/api/v1/account/{self.account_id}/models/{kb}")
            await root_request(self.auth, "POST", path, data={"id": model_id})

    async def list(self) -> list:
        path = get_regional_url(self.zone, f"/api/v1/account/{self.account_id}/models")
        models = await root_request(self.auth, "GET", path)
        assert models is not None
        assert isinstance(models, list)
        return models

    async def delete(self, model_id: str) -> None:
        path = get_regional_url(self.zone, f"/api/v1/account/{self.account_id}/model/{model_id}")
        await root_request(self.auth, "DELETE", path)

    async def remove_all(self) -> None:
        models = await self.list()
        for model in models:
            await self.delete(model["model_id"])


class DefaultModels:
    def __init__(
        self,
        auth: AsyncNucliaAuth,
        zone: str,
        account_id: str,
    ):
        self.auth = auth
        self.zone = zone
        self.account_id = account_id

    async def add(
        self,
        generative_model: str,
        model_data: dict,
    ) -> str:
        if "default_model_id" not in model_data:
            model_data["default_model_id"] = generative_model
        # Add model to the account
        path = get_regional_url(self.zone, f"/api/v1/account/{self.account_id}/default_models")
        response = await root_request(self.auth, "POST", path, data=model_data)
        assert response is not None
        model_id = response["id"]
        return model_id

    async def list(self) -> list:
        path = get_regional_url(self.zone, f"/api/v1/account/{self.account_id}/default_models")
        models = await root_request(self.auth, "GET", path)
        assert models is not None
        assert isinstance(models, list)
        return models

    async def delete(self, model_id: str) -> None:
        path = get_regional_url(self.zone, f"/api/v1/account/{self.account_id}/default_model/{model_id}")
        await root_request(self.auth, "DELETE", path)

    async def remove_all(self) -> None:
        models = await self.list()
        for model in models:
            await self.delete(model["id"])
