# On the SDK, the httpx client is instantiated in a lot of places, sometimes very deeply nested.
# With this we can increment the timeout for all requests to minimize noise caused specially by
# ReadTimeout and ConnectTimeout, related probably to where the tests run on GHA.
#
# This patch needs to be executed first
# fmt: off
from nuclia_e2e.tests.patch_httpx import patch_httpx; patch_httpx()  # noqa: I001,E702
# fmt: on
from collections.abc import AsyncIterator  # noqa: E402
from collections.abc import Generator  # noqa: E402
from copy import deepcopy  # noqa: E402
from datetime import datetime  # noqa: E402
from datetime import timedelta  # noqa: E402
from email.header import decode_header  # noqa: E402
from functools import partial  # noqa: E402
from nuclia import sdk  # noqa: E402
from nuclia.config import reset_config_file  # noqa: E402
from nuclia.config import set_config_file  # noqa: E402
from nuclia.data import get_async_auth  # noqa: E402
from nuclia.data import get_config  # noqa: E402
from nuclia.lib.nua import AsyncNuaClient  # noqa: E402
from nuclia.sdk.auth import AsyncNucliaAuth  # noqa: E402
from nuclia_e2e.data import TEST_ACCOUNT_SLUG  # noqa: E402
from nuclia_e2e.settings import settings  # noqa: E402
from nuclia_e2e.tests.utils import _tasks_to_delete  # noqa: E402
from nuclia_e2e.tests.utils import clean_ask_test_tasks  # noqa: E402
from nuclia_e2e.utils import get_async_kb_ndb_client  # noqa: E402
from nuclia_e2e.utils import Retriable  # noqa: E402

import aiohttp  # noqa: E402
import asyncio  # noqa: E402
import backoff  # noqa: E402
import dataclasses  # noqa: E402
import email  # noqa: E402
import imaplib  # noqa: E402
import logging  # noqa: E402
import nuclia  # noqa: E402
import os  # noqa: E402
import pytest  # noqa: E402
import random  # noqa: E402
import re  # noqa: E402
import string  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402

TEST_ENV = settings.test_env.lower()
GRAFANA_URL = settings.grafana_url
TEMPO_DATASOURCE_ID = "P95F6455D1776E941"  # is the same one on progress and our clusters


@dataclasses.dataclass(slots=True)
class GlobalConfig:
    name: str
    base_domain: str
    recaptcha: str
    root_pat_token: str
    permanent_account_owner_pat_token: str
    gmail_app_password: str
    permanent_account_slug: str
    permanent_account_id: str
    grafana_url: str
    tempo_datasource_id: str


@dataclasses.dataclass(slots=True)
class ZoneConfig:
    name: str
    zone_slug: str
    test_kb_slug: str
    permanent_nua_key: str
    permanent_kb_slug: str
    permanent_kb_id: str = ""
    global_config: GlobalConfig | None = None


@dataclasses.dataclass(slots=True)
class ClusterConfig:
    global_config: GlobalConfig
    zones: list[ZoneConfig]


# All tests that needs some existing account will use the one configured in
# the global "permanent_account_slug" with some predefined user credentials without expiration:
# "permanent_account_owner_pat": PAT token for `testing_sdk@nuclia.com` on the suitable account


CLUSTERS_CONFIG = {
    "prod": ClusterConfig(
        global_config=GlobalConfig(
            name="prod",
            base_domain="rag.progress.cloud",
            recaptcha=settings.prod_global_recaptcha,
            root_pat_token=settings.prod_root_pat_token,
            permanent_account_owner_pat_token=settings.prod_permament_account_owner_pat_token,
            gmail_app_password=settings.test_gmail_app_password,
            permanent_account_slug="automated-testing",
            permanent_account_id="8c7db65c-3b7e-4140-8165-d37bb4e6e9b8",
            grafana_url="https://grafana.gcp-internal-1.nuclia.cloud/",
            tempo_datasource_id=TEMPO_DATASOURCE_ID,
        ),
        zones=[
            ZoneConfig(
                name="gke-prod-1",
                zone_slug="europe-1",
                test_kb_slug="nuclia-e2e-live-europe-1",
                permanent_kb_slug="pre-existing-kb",
                permanent_nua_key=settings.prod_gcp_europe1_nua,
            ),
            ZoneConfig(
                name="aws-us-east-2-1",
                zone_slug="aws-us-east-2-1",
                test_kb_slug="nuclia-e2e-live-aws-us-east-2-1",
                permanent_kb_slug="pre-existing-kb",
                permanent_nua_key=settings.prod_aws_us_east_2_1_nua,
            ),
            ZoneConfig(
                name="aws-il-central-1-1",
                zone_slug="aws-il-central-1-1",
                test_kb_slug="nuclia-e2e-live-aws-il-central-1-1",
                permanent_kb_slug="pre-existing-kb",
                permanent_nua_key=settings.prod_aws_il_central_1_1_nua,
            ),
            ZoneConfig(
                name="aws-eu-central-1-1",
                zone_slug="aws-eu-central-1-1",
                test_kb_slug="nuclia-e2e-live-aws-eu-central-1-1",
                permanent_kb_slug="pre-existing-kb",
                permanent_nua_key=settings.prod_aws_eu_central_1_1_nua,
            ),
            ZoneConfig(
                name="aws-me-central-1-1",
                zone_slug="aws-me-central-1-1",
                test_kb_slug="nuclia-e2e-live-aws-me-central-1-1",
                permanent_kb_slug="pre-existing-kb",
                permanent_nua_key=settings.prod_aws_me_central_1_1_nua,
            ),
            ZoneConfig(
                name="aws-ap-southeast-2-1",
                zone_slug="aws-ap-southeast-2-1",
                test_kb_slug="nuclia-e2e-live-aws-ap-southeast-2-1",
                permanent_kb_slug="aws-australia-pre-existing-kb",
                permanent_nua_key=settings.prod_aws_ap_southeast_2_1_nua,
            ),
        ],
    ),
    "stage": ClusterConfig(
        global_config=GlobalConfig(
            name="stage",
            base_domain="stashify.cloud",
            recaptcha=settings.stage_global_recaptcha,
            root_pat_token=settings.stage_root_pat_token,
            permanent_account_owner_pat_token=settings.stage_permament_account_owner_pat_token,
            gmail_app_password=settings.test_gmail_app_password,
            permanent_account_slug="automated-testing",
            permanent_account_id="f2edd58e-431f-4197-be76-6fc611082fe8",
            grafana_url="http://platform.grafana.nuclia.com",
            tempo_datasource_id=TEMPO_DATASOURCE_ID,
        ),
        zones=[
            ZoneConfig(
                name="gke-stage-1",
                zone_slug="europe-1",
                test_kb_slug="nuclia-e2e-live-europe-1",
                permanent_kb_slug="pre-existing-kb",
                permanent_nua_key=settings.stage_gcp_europe1_nua,
            )
        ],
    )
}

TEST_CLUSTER = CLUSTERS_CONFIG[TEST_ENV.lower()]

ALL_TEST_ZONES = [zone.name for zone in TEST_CLUSTER.zones]
if settings.test_zones is None:
    ENABLED_ZONES = ALL_TEST_ZONES
else:
    ENABLED_ZONES = [zone.strip(" ") for zone in settings.test_zones.split(",") if zone.strip(" ")]
TEST_CLUSTER.zones = [zone for zone in TEST_CLUSTER.zones if zone.name in ENABLED_ZONES]

if not TEST_CLUSTER.zones:
    print("Exiting, no zones defined or all of them filtered")
    sys.exit(1)


class ManagerAPI:
    def __init__(self, global_api, session: aiohttp.ClientSession):
        self.global_api = global_api
        self.session = session

    async def delete_account(self, account_slug) -> bool:
        url = f"{self.global_api.base_url}/api/manage/@account/{account_slug}"
        async with self.session.delete(url, headers=self.global_api.root_auth_headers) as response:
            if response.status not in (204, 404):
                response.raise_for_status()
            return response.status == 204


class GlobalAPI:
    def __init__(self, base_url, recaptcha, root_pat_token, session: aiohttp.ClientSession):
        self.base_url = base_url
        self.recaptcha = recaptcha
        self.root_pat_token = root_pat_token
        self.access_token = None
        self.session = session
        self.manager = ManagerAPI(self, self.session)

    @property
    def auth_headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
        }

    @property
    def root_auth_headers(self):
        return {
            "Authorization": f"Bearer {self.root_pat_token}",
        }

    async def signup(self, name, email, password):
        url = f"{self.base_url}/api/auth/signup"
        payload = {"name": name, "email": email, "password": password}
        headers = {"X-STF-VALIDATION": self.recaptcha}
        async with self.session.post(url, json=payload, headers=headers) as response:
            response.raise_for_status()
            return await response.json()

    async def finalize_signup(self, signup_token):
        url = f"{self.base_url}/api/auth/magic?token={signup_token}"
        async with self.session.post(url) as response:
            response.raise_for_status()
            return await response.json()

    def set_access_token(self, access_token):
        self.access_token = access_token

    async def send_onboard_inquiry(self, data):
        url = f"{self.base_url}/api/v1/user/onboarding_inquiry"
        async with self.session.put(url, json=data, headers=self.auth_headers) as response:
            response.raise_for_status()

    async def create_account(self, slug):
        if not self.access_token:
            msg = "Access token is not set. Please provide an access token."
            raise ValueError(msg)
        url = f"{self.base_url}/api/v1/accounts"
        async with self.session.post(
            url, json={"slug": slug, "title": slug}, headers=self.auth_headers
        ) as response:
            response.raise_for_status()
            return (await response.json())["id"]

    async def get_usage(self, account_id, kb_id, from_date, to_date):
        params = f"from={from_date}&to={to_date}&knowledgebox={kb_id}"
        url = f"{self.base_url}/api/v1/account/{account_id}/usage?{params}"
        async with self.session.get(url, headers=self.root_auth_headers) as response:
            response.raise_for_status()
            return await response.json()


class RegionalAPI:
    def __init__(self, base_url, access_token, session: aiohttp.ClientSession):
        self.base_url = base_url
        self.access_token = access_token
        self.session = session

    @property
    def auth_headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
        }

    async def get_kb_sa(self, account: str, kbid: str) -> list[dict[str, str]]:
        url = f"{self.base_url}/api/v1/account/{account}/kb/{kbid}/service_accounts"
        async with self.session.get(url, headers=self.auth_headers) as response:
            data = await response.json()
            return [{"id": sa["id"], "title": sa["title"]} for sa in data]

    async def create_service_account(
        self, account: str, kbid: str, service_account_name: str, role: str = "SOWNER"
    ) -> dict[str, str]:
        url = f"{self.base_url}/api/v1/account/{account}/kb/{kbid}/service_accounts"
        async with self.session.post(
            url, headers=self.auth_headers, json={"title": service_account_name, "role": role}
        ) as response:
            data = await response.json()
            return data

    async def create_service_account_key(self, account: str, kbid: str, sa_id: str, ttl=60 * 60 * 24) -> str:
        url = f"{self.base_url}/api/v1/account/{account}/kb/{kbid}/service_account/{sa_id}/keys"
        expires = datetime.now() + timedelta(seconds=ttl)
        async with self.session.post(
            url, headers=self.auth_headers, json={"expires": expires.strftime("%Y-%m-%dT%H:%M:%SZ")}
        ) as response:
            data = await response.json()
            return data["token"]

    async def create_service_account_temp_key(self, sa_token: str, security_groups: list[str] | None) -> str:
        url = f"{self.base_url}/api/v1/service_account_temporal_key"
        payload = {} if security_groups is None else {"security_groups": security_groups}

        async with self.session.post(
            url, headers={"x-nuclia-serviceaccount": f"Bearer {sa_token}"}, json=payload
        ) as response:
            data = await response.json()
            return data["token"]

    async def delete_service_account_by_name(
        self, account: str, kbid: str, service_account_name: str
    ) -> str | None:
        kb_sa = await self.get_kb_sa(account, kbid)
        test_sa = [a for a in kb_sa if a["title"] == service_account_name]
        if len(test_sa) != 1:
            return None
        sa_id = test_sa[0]["id"]
        url = f"{self.base_url}/api/v1/account/{account}/kb/{kbid}/service_account/{sa_id}"
        async with self.session.delete(url, headers=self.auth_headers) as response:
            response.raise_for_status()
        return sa_id

    async def create_vector_set(self, kb_id: str, model: str):
        url = f"{self.base_url}/api/v1/kb/{kb_id}/vectorsets/{model}"
        async with self.session.post(url, headers=self.auth_headers) as response:
            response.raise_for_status()

    async def delete_vector_set(self, kb_id: str, model: str):
        url = f"{self.base_url}/api/v1/kb/{kb_id}/vectorsets/{model}"
        async with self.session.delete(url, headers=self.auth_headers) as response:
            response.raise_for_status()

    async def get_configuration(self, kb_id: str) -> dict:
        url = f"{self.base_url}/api/v1/kb/{kb_id}/configuration"
        async with self.session.get(url, headers=self.auth_headers) as response:
            response.raise_for_status()
            return await response.json()

    @backoff.on_exception(
        backoff.expo,
        aiohttp.ClientResponseError,
        max_tries=6,
        max_time=120,
        giveup=lambda exc: not (isinstance(exc, aiohttp.ClientResponseError) and exc.status == 429),
    )
    async def create_rao(self, account_id: str, slug: str, mode: str = "agent_no_memory") -> dict:
        url = f"{self.base_url}/api/v1/account/{account_id}/kbs"
        async with self.session.post(
            url,
            json={
                "title": slug,
                "slug": slug,
                "mode": mode,
            },
            headers=self.auth_headers,
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def rao(
        self,
        method: str,
        agent_id: str,
        endpoint: str,
        payload: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        url = f"{self.base_url}/api/v1/agent/{agent_id}/{endpoint}"
        async with self.session.request(
            method, url, json=payload, headers=self.auth_headers, params=params
        ) as response:
            response.raise_for_status()
            return await response.json()


@pytest.fixture(autouse=True)
def set_logger_level():
    logger = logging.getLogger("nuclia-sdk")
    logger.setLevel(logging.CRITICAL)


@pytest.fixture
async def aiohttp_session():
    """
    Create a shared aiohttp session for the entire test session.
    """
    async with aiohttp.ClientSession() as session:
        yield session


@pytest.fixture
def global_api(aiohttp_session, global_api_config):
    """
    Provide a configured GlobalAPI instance for tests.
    """
    return GlobalAPI(
        f"https://{global_api_config.base_domain}",
        global_api_config.recaptcha,
        global_api_config.root_pat_token,
        aiohttp_session,
    )


@pytest.fixture
async def regional_api(aiohttp_session, global_api_config, regional_api_config):
    """
    Provide a configured GlobalAPI instance for tests.
    """
    return RegionalAPI(
        nuclia.REGIONAL.format(region=regional_api_config.zone_slug),
        global_api_config.permanent_account_owner_pat_token,
        aiohttp_session,
    )


@pytest.fixture
def global_api_config() -> Generator[GlobalConfig, None, None]:
    global_config = TEST_CLUSTER.global_config
    nuclia.BASE_DOMAIN = global_config.base_domain
    # regenerate all urls based on the new base domain
    nuclia.CLOUD_ID = nuclia.BASE_DOMAIN
    nuclia.REGIONAL = nuclia._regional_template(nuclia.BASE_DOMAIN)
    nuclia.OAUTH_BASE = nuclia.get_oauth_base(nuclia.BASE_DOMAIN)
    nuclia.GLOBAL_BASE = nuclia.get_global_base(nuclia.BASE_DOMAIN)
    os.environ["TESTING"] = "True"
    with tempfile.NamedTemporaryFile() as temp_file:
        temp_file.write(b"{}")
        temp_file.flush()
        set_config_file(temp_file.name)
        yield global_config
        reset_config_file()


@pytest.fixture(params=[pytest.param(zone, id=zone.name) for zone in TEST_CLUSTER.zones])
async def regional_api_config(request: pytest.FixtureRequest, global_api_config: GlobalConfig) -> ZoneConfig:
    zone_config: ZoneConfig = deepcopy(request.param)
    auth = get_async_auth()
    config = get_config()
    await auth.set_user_token(global_api_config.permanent_account_owner_pat_token)
    config.set_default_account(global_api_config.permanent_account_slug)
    config.set_default_zone(zone_config.zone_slug)
    # Store a reference for convenience
    zone_config.global_config = global_api_config

    return zone_config


async def resolve_permanent_kb_id(zone_config: ZoneConfig) -> str:
    if zone_config.permanent_kb_id:
        return zone_config.permanent_kb_id
    assert zone_config.global_config is not None

    auth = get_async_auth()
    account_id = zone_config.global_config.permanent_account_id
    try:
        knowledge_boxes = await auth.kbs(account_id, zone=zone_config.zone_slug)
    except TypeError:
        knowledge_boxes = [kb for kb in await auth.kbs(account_id) if kb.region == zone_config.zone_slug]

    kbs = {kb.slug: kb.id for kb in knowledge_boxes if kb.slug is not None}
    kb_id = kbs.get(zone_config.permanent_kb_slug)
    if kb_id is None:
        available_slugs = ", ".join(sorted(kbs)) or "<none>"
        pytest.fail(
            f"Permanent KB '{zone_config.permanent_kb_slug}' was not found in "
            f"account '{account_id}' for zone '{zone_config.zone_slug}'. "
            f"Available KB slugs: {available_slugs}"
        )
    zone_config.permanent_kb_id = kb_id
    return kb_id


class EmailUtil:
    def __init__(self, base_address, gmail_app_password):
        self.base_address = base_address
        self.gmail_app_password = gmail_app_password

    def generate_email_address(self):
        user, domain = self.base_address.split("@")
        random_string = "".join(random.choices(string.ascii_letters + string.digits, k=8)).lower()
        return f"{user}++testing++{random_string}@{domain}"

    async def get_last_email_body(self, test_address):
        """
        Retrieves the HTML content of the last email sent to the specified test address.
        """
        # Connect to Gmail
        imap_host = "imap.gmail.com"
        username = self.base_address
        password = self.gmail_app_password

        mail = imaplib.IMAP4_SSL(imap_host)
        await asyncio.to_thread(partial(mail.login, username, password))
        mail.select("inbox")

        # Search for emails targeted to the specific email variant
        status, messages = await asyncio.to_thread(partial(mail.search, None, "TO", f'"{test_address}"'))
        mail_ids = messages[0].split()
        if not mail_ids:
            return None  # No emails found

        # Get the last email ID
        last_mail_id = mail_ids[-1]
        _, msg_data = mail.fetch(last_mail_id, "(RFC822)")

        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])

                # Decode the subject (optional, can be removed if not needed)
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else "utf-8")

                # Extract HTML content
                html_content = None
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        if content_type == "text/html":
                            html_content = part.get_payload(decode=True).decode()
                            break  # Stop after finding the first HTML part
                # For non-multipart emails
                elif msg.get_content_type() == "text/html":
                    html_content = msg.get_payload(decode=True).decode()

                mail.logout()
                return html_content
        try:
            mail.logout()
        except Exception:
            return None

    async def wait_for_email_signup_link(self, email_address, max_wait_time=20):
        print(f"waiting 10 seconds for signup email at {email_address}")
        signup_url = None
        for _ in range(max_wait_time):
            print("still waiting...")
            await asyncio.sleep(1)
            body = await self.get_last_email_body(email_address)
            if body:
                # Find URLs containing "ls/click". This is to identify sendgrid "wrapping" for click tracking
                urls = re.findall(r"(https?://.*?ls/click.*?['\"])", body)
                if urls:
                    signup_url = urls[0].rstrip('"').rstrip("'")
                return signup_url
        return signup_url


@pytest.fixture
def email_util(global_api_config):
    return EmailUtil("nucliaemailvalidation@gmail.com", global_api_config.gmail_app_password)


@pytest.fixture
async def cleanup_test_account(global_api: GlobalAPI):
    await global_api.manager.delete_account(TEST_ACCOUNT_SLUG)

    yield

    await global_api.manager.delete_account(TEST_ACCOUNT_SLUG)


@pytest.fixture
async def clean_kb_sa(
    request: pytest.FixtureRequest, regional_api_config, regional_api: RegionalAPI, kb_id: str
):
    deleted_sa_id = await regional_api.delete_service_account_by_name(
        regional_api_config.global_config.permanent_account_id,
        kb_id,
        "test-e2e-kb-auth",
    )
    if deleted_sa_id:
        print(f"clean_kb_sa fixture: Deleted service account with id: {deleted_sa_id}")


@pytest.fixture
async def nua_client(regional_api_config) -> AsyncNuaClient:
    nc = AsyncNuaClient(
        region=nuclia.REGIONAL.format(region=regional_api_config.zone_slug),
        account=regional_api_config.global_config.permanent_account_id,
        token=regional_api_config.permanent_nua_key,
    )
    return Retriable.wrap_async(nc)


@pytest.fixture
async def kb_id(regional_api_config: ZoneConfig) -> str:
    """
    Fixture to provide the knowledge base ID for the tests.
    """
    return await resolve_permanent_kb_id(regional_api_config)


@pytest.fixture
async def zone(regional_api_config: ZoneConfig) -> str:
    """
    Fixture to provide the zone slug for the tests.
    """
    return regional_api_config.zone_slug


@pytest.fixture
def auth() -> AsyncNucliaAuth:
    """
    Fixture to provide the async Nuclia authentication object.
    """
    return get_async_auth()


@pytest.fixture(autouse=True)
async def account_id(regional_api_config: ZoneConfig) -> str:
    """
    Fixture to provide the account slug for the tests.
    """
    assert regional_api_config.global_config is not None
    return regional_api_config.global_config.permanent_account_id


@pytest.fixture
async def clean_tasks(kb_id: str, zone: str, auth: AsyncNucliaAuth) -> AsyncIterator[None]:
    ndb = get_async_kb_ndb_client(zone=zone, kbid=kb_id, user_token=auth._config.token)
    kb = sdk.AsyncNucliaKB()

    yield

    if _tasks_to_delete:
        await clean_ask_test_tasks(kb, ndb, to_delete=_tasks_to_delete)
        _tasks_to_delete.clear()
