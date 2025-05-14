from collections.abc import Awaitable
from collections.abc import Callable
from nuclia.lib.kb import AsyncNucliaDBClient
from nuclia.lib.kb import Environment
from nuclia.lib.kb import NucliaDBClient
from nuclia.sdk.kbs import AsyncNucliaKBS
from pathlib import Path
from time import monotonic
from typing import Any

from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

import asyncio

ASSETS_FILE_PATH = Path(__file__).parent.joinpath("assets")
NUCLIADB_KB_ENDPOINT = "/api/v1/kb/{kb}"


Logger = Callable[[str], None]


def get_asset_file_path(file: str):
    return str(ASSETS_FILE_PATH.joinpath(file))


async def create_test_kb(regional_api_config, kb_slug, logger: Logger = print) -> str:
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

async def delete_test_kb(regional_api_config, kbid, kb_slug, logger):
    kbs = AsyncNucliaKBS()
    logger("Deleting kb {kbid}")
    await kbs.delete(zone=regional_api_config.zone_slug, id=kbid)

    kbid = await get_kbid_from_slug(regional_api_config.zone_slug, kb_slug)
    assert kbid is None

async def wait_for(
    condition: Callable[[], Awaitable[tuple[bool, Any]]],
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
    logger(f"wait_for '{func_name}' success={success} in {monotonic() - start} seconds")
    return success, data


async def get_kbid_from_slug(zone: str, slug: str) -> str | None:
    kbs = AsyncNucliaKBS()
    all_kbs = await kbs.list()
    kbids_by_slug = {kb.slug: kb.id for kb in all_kbs}
    kbid = kbids_by_slug.get(slug)
    return kbid


def get_async_kb_ndb_client(
    zone: str,
    kbid: str,
    user_token: str | None = None,
    service_account_token: str | None = None,
) -> AsyncNucliaDBClient:
    from nuclia import REGIONAL

    assert any((user_token, service_account_token)), "One of user_token or service_account_token must be set"

    kb_path = NUCLIADB_KB_ENDPOINT.format(kb=kbid)
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


def make_retry_async(attempts=3, delay=10):
    return retry(
        stop=stop_after_attempt(attempts),
        wait=wait_fixed(delay),
        reraise=True,
    )
