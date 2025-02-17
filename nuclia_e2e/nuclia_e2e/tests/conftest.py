# fmt: off
# Save the original __init__ method
import httpx  # noqa: I001
_original_init = httpx.AsyncClient.__init__

def custom_init(self, *args, timeout=httpx.Timeout(100), **kwargs):
    """Override httpx.Client.__init__ to set a custom default timeout."""
    if "timeout" not in kwargs:  # Only override if timeout is not explicitly set
        kwargs["timeout"] = timeout
    _original_init(self, *args, **kwargs)  # Call original init


# Apply the patch
httpx.AsyncClient.__init__ = custom_init
# fmt: on

from copy import deepcopy
from datetime import datetime
from datetime import timedelta
from email.header import decode_header
from functools import partial
from nuclia.config import reset_config_file
from nuclia.config import set_config_file
from nuclia.data import get_async_auth
from nuclia.data import get_config
from nuclia.lib.nua import AsyncNuaClient
from nuclia.sdk.kbs import NucliaKBS
from nuclia_e2e.data import TEST_ACCOUNT_SLUG

import aiohttp
import asyncio
import email
import imaplib
import nuclia
import os
import pytest
import random
import re
import string
import tempfile

TEST_ENV = os.environ.get("TEST_ENV")

# All tests that needs some existing account will use the one configured in
# the global "permanent_account_slug" with some predefined user credentials without expiration:
# "permanent_account_owner_pat": PAT token for `testing_sdk@nuclia.com` on the suitable account

CLUSTERS_CONFIG = {
    "prod": {
        "global": {
            "base_domain": "nuclia.cloud",
            "recaptcha": os.environ.get("PROD_GLOBAL_RECAPTCHA"),
            "root_pat_token": os.environ.get("PROD_ROOT_PAT_TOKEN"),
            "permanent_account_slug": "automated-testing",
            "permanent_account_owner_pat_token": os.environ.get("PROD_PERMAMENT_ACCOUNT_OWNER_PAT_TOKEN"),
            "gmail_app_password": os.environ.get("TEST_GMAIL_APP_PASSWORD"),
        },
        "zones": [
            {
                "name": "europe-1",
                "zone_slug": "europe-1",
                "test_kb_slug": "nuclia-e2e-live",
                "permanent_kb_slug": "pre-existing-kb",
                "permanent_nua_key": os.environ.get("TEST_EUROPE1_NUCLIA_NUA"),
            },
            {
                "name": "aws-us-east-2-1",
                "zone_slug": "aws-us-east-2-1",
                "test_kb_slug": "nuclia-e2e-live",
                "permanent_kb_slug": "pre-existing-kb",
                "permanent_nua_key": os.environ.get("TEST_AWS_US_EAST_2_1_NUCLIA_NUA"),
            },
        ],
    },
    "stage": {
        "global": {
            "base_domain": "stashify.cloud",
            "recaptcha": os.environ.get("STAGE_GLOBAL_RECAPTCHA"),
            "root_pat_token": os.environ.get("STAGE_ROOT_PAT_TOKEN"),
            "permanent_account_slug": "automated-testing",
            "permanent_account_owner_pat_token": os.environ.get("STAGE_PERMAMENT_ACCOUNT_OWNER_PAT_TOKEN"),
            "gmail_app_password": os.environ.get("TEST_GMAIL_APP_PASSWORD"),
        },
        "zones": [
            {
                "name": "europe-1",
                "zone_slug": "europe-1",
                "test_kb_slug": "nuclia-e2e-live",
                "permanent_kb_slug": "pre-existing-kb",
                "permanent_nua_key": os.environ.get("TEST_EUROPE1_STASHIFY_NUA"),
            },
            # uncomment to test two zone parallel testing on stage
            # {
            #     "name": "europe-2",
            #     "zone_slug": "europe-1",
            #     "test_kb_slug": "nuclia-e2e-live"
            # }
        ],
    },
}


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
            url, headers=self.auth_headers, json={"expires": expires.isoformat()}
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
        f"https://{global_api_config['base_domain']}",
        global_api_config["recaptcha"],
        global_api_config["root_pat_token"],
        aiohttp_session,
    )


@pytest.fixture
async def regional_api(aiohttp_session, global_api_config, regional_api_config):
    """
    Provide a configured GlobalAPI instance for tests.
    """
    return RegionalAPI(
        nuclia.REGIONAL.format(region=regional_api_config["zone_slug"]),
        global_api_config["permanent_account_owner_pat_token"],
        aiohttp_session,
    )


@pytest.fixture
def global_api_config():
    global_config = CLUSTERS_CONFIG[TEST_ENV]["global"]
    nuclia.BASE = f"https://{global_config['base_domain']}"
    nuclia.REGIONAL = f"https://{{region}}.{global_config['base_domain']}"
    os.environ["TESTING"] = "True"
    with tempfile.NamedTemporaryFile() as temp_file:
        temp_file.write(b"{}")
        temp_file.flush()
        set_config_file(temp_file.name)
        yield global_config
        reset_config_file()


@pytest.fixture(
    params=[pytest.param(zone, id=zone["name"]) for zone in CLUSTERS_CONFIG[TEST_ENV]["zones"]],
)
async def regional_api_config(request: pytest.FixtureRequest, global_api_config):
    zone_config = deepcopy(request.param)
    auth = get_async_auth()
    config = get_config()
    await auth.set_user_token(global_api_config["permanent_account_owner_pat_token"])
    config.set_default_account(global_api_config["permanent_account_slug"])
    config.set_default_zone(zone_config["zone_slug"])
    zone_config["test_kb_slug"] = "{test_kb_slug}-{name}".format(**zone_config)
    zone_config["permanent_account_slug"] = global_api_config["permanent_account_slug"]
    zone_config["permanent_account_id"] = {a.slug: a.id for a in config.accounts}[
        global_api_config["permanent_account_slug"]
    ]

    kbs = {
        kb.slug: kb.id
        for kb in await auth.kbs(zone_config["permanent_account_id"])
        if kb.region == zone_config["zone_slug"]
    }
    zone_config["permanent_kb_id"] = kbs[zone_config["permanent_kb_slug"]]

    return zone_config


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
    return EmailUtil("nucliaemailvalidation@gmail.com", global_api_config["gmail_app_password"])


@pytest.fixture
async def cleanup_test_account(global_api: GlobalAPI):
    await global_api.manager.delete_account(TEST_ACCOUNT_SLUG)

    yield

    await global_api.manager.delete_account(TEST_ACCOUNT_SLUG)


@pytest.fixture
async def clean_kb_test(request: pytest.FixtureRequest, regional_api_config):
    kbs = NucliaKBS()
    kb_slug = regional_api_config["test_kb_slug"]
    all_kbs = await asyncio.to_thread(kbs.list)
    kb_ids_by_slug = {kb.slug: kb.id for kb in all_kbs}
    kb_id = kb_ids_by_slug.get(kb_slug)
    try:
        await asyncio.to_thread(partial(kbs.delete, zone=regional_api_config["zone_slug"], id=kb_id))
    except ValueError:
        # Raised by sdk when kb not found
        pass


@pytest.fixture
async def clean_kb_sa(request: pytest.FixtureRequest, regional_api_config, regional_api: RegionalAPI):
    deleted_sa_id = await regional_api.delete_service_account_by_name(
        regional_api_config["permanent_account_id"],
        regional_api_config["permanent_kb_id"],
        "test-e2e-kb-auth",
    )
    if deleted_sa_id:
        print(f"clean_kb_sa fixture: Deleted service account with id: {deleted_sa_id}")


@pytest.fixture
async def nua_client(regional_api_config):
    nc = AsyncNuaClient(
        region=nuclia.REGIONAL.format(region=regional_api_config["zone_slug"]),
        account=regional_api_config["permanent_account_id"],
        token=regional_api_config["permanent_nua_key"],
    )
    return nc
