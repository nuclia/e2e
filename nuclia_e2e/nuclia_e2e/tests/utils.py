from collections.abc import AsyncIterator
from nuclia import sdk
from nuclia.lib.kb import AsyncNucliaDBClient
from nuclia.sdk.auth import AsyncNucliaAuth
from nuclia_e2e.utils import get_async_kb_ndb_client
from nucliadb_sdk.v2.exceptions import NotFoundError

import contextlib
import os


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
async def as_kb_default_generative_model(
    kb_id: str, zone: str, auth: AsyncNucliaAuth, generative_model: str
) -> AsyncIterator[None]:
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
