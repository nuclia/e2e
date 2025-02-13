from collections.abc import Awaitable
from collections.abc import Callable
from nuclia.lib.kb import AsyncNucliaDBClient
from nuclia.lib.kb import Environment
from nuclia.lib.kb import NucliaDBClient
from nuclia.sdk.kbs import NucliaKBS
from pathlib import Path
from time import monotonic
from typing import Any

import asyncio

ASSETS_FILE_PATH = Path(__file__).parent.joinpath("assets")
NUCLIADB_KB_ENDPOINT = "/api/v1/kb/{kb}"


Logger = Callable[[str], None]


def get_asset_file_path(file: str):
    return str(ASSETS_FILE_PATH.joinpath(file))


async def wait_for(
    condition: Callable[[], Awaitable],
    max_wait: int = 60,
    interval: int = 5,
    logger: Logger = print,
) -> tuple[bool, Any]:
    func_name = condition.__name__
    logger(f"start wait_for '{func_name}', max_wait={max_wait}s")
    start = monotonic()
    success, data = await condition()
    while not success and monotonic() - start < max_wait:
        await asyncio.sleep(interval)
        success, data = await condition()
    logger(f"wait_for '{func_name}' success={success} in {monotonic()-start} seconds")
    return success, data


async def get_kbid_from_slug(zone: str, slug: str) -> str | None:
    kbs = NucliaKBS()
    all_kbs = await asyncio.to_thread(kbs.list)
    kbids_by_slug = {kb.slug: kb.id for kb in all_kbs}
    kbid = kbids_by_slug.get(slug)
    return kbid


def get_async_kb_ndb_client(
    zone: str,
    account: str,
    kbid: str,
    user_token: str | None = None,
    service_account_token: str | None = None,
) -> AsyncNucliaDBClient:
    from nuclia import REGIONAL

    assert any((user_token, service_account_token)), "One of user_token or service_account_token must be set"

    kb_path = NUCLIADB_KB_ENDPOINT.format(zone=zone, account=account, kb=kbid)
    base_url = REGIONAL.format(region=zone)
    kb_base_url = f"{base_url}{kb_path}"

    auth_params = {}

    if user_token is not None:
        auth_params["user_token"] = user_token
    elif service_account_token is not None:
        auth_params["api_key"] = service_account_token

    ndb = AsyncNucliaDBClient(environment=Environment.CLOUD, url=kb_base_url, region=zone, **auth_params)
    return ndb


def get_sync_kb_ndb_client(
    zone: str,
    account: str,
    kbid: str,
    user_token: str | None = None,
    service_account_token: str | None = None,
) -> NucliaDBClient:
    from nuclia import REGIONAL

    assert any((user_token, service_account_token)), "One of user_token or service_account_token must be set"

    kb_path = NUCLIADB_KB_ENDPOINT.format(zone=zone, account=account, kb=kbid)
    base_url = REGIONAL.format(region=zone)
    kb_base_url = f"{base_url}{kb_path}"

    auth_params = {}

    if user_token is not None:
        auth_params["user_token"] = user_token
    elif service_account_token is not None:
        auth_params["api_key"] = service_account_token

    ndb = NucliaDBClient(environment=Environment.CLOUD, url=kb_base_url, region=zone, **auth_params)
    return ndb
