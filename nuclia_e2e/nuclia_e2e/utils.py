from collections.abc import Awaitable
from collections.abc import Callable
from functools import wraps
from nuclia.exceptions import NuaAPIException
from nuclia.lib.kb import AsyncNucliaDBClient
from nuclia.lib.kb import Environment
from nuclia.lib.kb import NucliaDBClient
from nuclia.sdk.agents import AsyncNucliaAgents
from nuclia.sdk.kbs import AsyncNucliaKBS
from pathlib import Path
from tenacity import retry
from tenacity import retry_if_exception
from tenacity import retry_if_exception_type
from tenacity import RetryCallState
from tenacity import stop_after_attempt
from tenacity import wait_fixed
from tenacity import wait_random
from time import monotonic
from typing import cast
from typing import ClassVar
from typing import Generic
from typing import TypeVar

import asyncio
import httpx
import inspect
import nucliadb_sdk
import re
import requests

ASSETS_FILE_PATH = Path(__file__).parent.joinpath("assets")
NUCLIADB_KB_ENDPOINT = "/api/v1/kb/{kb}"

Logger = Callable[[str], None]


T = TypeVar("T")


def get_asset_file_path(file: str):
    return str(ASSETS_FILE_PATH.joinpath(file))


def _is_kb_creation_rate_limited(exc: BaseException) -> bool:
    return "429" in str(exc)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_random(2, 10),
    retry=retry_if_exception(_is_kb_creation_rate_limited),
    reraise=True,
)
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


async def delete_test_kb(regional_api_config, kbid, kb_slug, logger=print):
    kbs = AsyncNucliaKBS()
    logger(f"Deleting kb {kbid}")
    await kbs.delete(zone=regional_api_config.zone_slug, id=kbid)

    kbid = await get_kbid_from_slug(regional_api_config.zone_slug, kb_slug)
    assert kbid is None


async def wait_for(
    condition: Callable[[], Awaitable[tuple[bool, T]]],
    max_wait: float = 60,
    interval: float = 5,
    logger: Logger = print,
) -> tuple[bool, T]:
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


async def get_agent_from_slug(zone: str, slug: str) -> str | None:
    agents = AsyncNucliaAgents()
    all_agents = await agents.list()
    agentids_by_slug = {agent.slug: agent.id for agent in all_agents}
    agentid = agentids_by_slug.get(slug)
    return agentid


async def delete_test_agent(regional_api_config, agent_id, agent_slug, logger=print):
    # Via kbs since AsyncNucliaAgents doesn't have delete method yet
    agents = AsyncNucliaKBS()
    logger(f"Deleting agent {agent_id}")
    await agents.delete(zone=regional_api_config.zone_slug, id=agent_id)


class Retriable(Generic[T]):
    RETRIABLE_STATUS_CODES: ClassVar[set[int]] = {502, 503, 504, 512}

    def __init__(self, client: T, is_async: bool):  # noqa: FBT001
        self._client = client
        self._is_async = is_async
        self.max_attempts = 24

    def __getattr__(self, name: str):
        attr = getattr(self._client, name)

        if callable(attr) and not name.startswith("_"):
            if self._is_async and inspect.iscoroutinefunction(attr):
                return self._wrap_async(attr, name)
            if not self._is_async and not inspect.iscoroutinefunction(attr):
                return self._wrap_sync(attr, name)
        return attr

    def _wrap_sync(self, func: Callable, func_name: str):
        @wraps(func)
        @self._retry_on_transient_errors(func_name)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    def _wrap_async(self, func: Callable, func_name: str):
        @wraps(func)
        @self._retry_on_transient_errors(func_name)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper

    def _retry_on_transient_errors(self, func_name: str):
        def log_before_sleep(retry_state: RetryCallState):
            attempt = retry_state.attempt_number
            assert retry_state.outcome is not None
            exc = retry_state.outcome.exception()
            print(
                f"[Retry #{attempt}/{self.max_attempts}] "
                f"Retrying '{func_name}' due to {type(exc).__name__}: {exc}"
            )

        # Wait up to 2 minutes,
        return retry(
            stop=stop_after_attempt(self.max_attempts),
            wait=wait_fixed(5),
            retry=retry_if_exception(self._is_transient_exception),
            before_sleep=log_before_sleep,
            reraise=True,
        )

    def _is_transient_exception(self, exc: BaseException) -> bool:
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in self.RETRIABLE_STATUS_CODES

        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            return exc.response.status_code in self.RETRIABLE_STATUS_CODES

        if isinstance(exc, NuaAPIException):
            return getattr(exc, "code", None) in self.RETRIABLE_STATUS_CODES

        # This is hacky, would be better to fix the nuclia.py to return a better exception, but i didn't want
        # to mess with the sdk that has been raising those exceptions for long, only for the tests...
        if isinstance(exc, RuntimeError | nucliadb_sdk.v2.exceptions.UnknownError):
            codes = "|".join(map(str, self.RETRIABLE_STATUS_CODES))
            match = re.search(rf"[^\d]({codes})[^\d]", str(exc))
            return match is not None

        # Maybe this is not transient, but as we cannot see for sue the source of this errors, probably always
        # some networking, we'll retry anyway, if it does all retries, then probably there's something pretty
        # broken
        if isinstance(exc, httpx.ReadError | httpx.RemoteProtocolError):  # noqa: SIM103
            return True

        return False

    @classmethod
    def wrap_sync(cls, client: T) -> T:
        return cast("T", cls(client, is_async=False))

    @classmethod
    def wrap_async(cls, client: T) -> T:
        return cast("T", cls(client, is_async=True))


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
    return Retriable.wrap_async(ndb)


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
    return Retriable.wrap_sync(ndb)


def make_retry_async(attempts=3, delay=10, exceptions=None):
    def _log_before_sleep(retry_state: RetryCallState):
        assert retry_state.fn is not None
        fn_name = retry_state.fn.__name__
        attempt_number = retry_state.attempt_number
        assert retry_state.outcome is not None
        exception = retry_state.outcome.exception()
        print(
            f"[Retry] Attempt {attempt_number} for function '{fn_name}'"
            f" due to {type(exception).__name__}: {exception}"
        )

    kwargs = {
        "stop": stop_after_attempt(attempts),
        "wait": wait_fixed(delay),
        "before_sleep": _log_before_sleep,
        "reraise": True,
    }

    if exceptions:
        kwargs["retry"] = retry_if_exception_type(tuple(exceptions))

    return retry(**kwargs)
