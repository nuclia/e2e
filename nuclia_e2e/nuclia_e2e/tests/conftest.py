from copy import deepcopy
from email.header import decode_header
from functools import partial
from nuclia.config import reset_config_file
from nuclia.config import set_config_file
from nuclia.data import get_auth
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
        },
        "zones": [
            {
                "name": "europe-1",
                "zone_slug": "europe-1",
                "test_kb_slug": "nuclia-e2e-live",
                "permanent_nua_key": os.environ.get("TEST_EUROPE1_NUCLIA_NUA"),
            },
            {
                "name": "aws-us-east-2-1",
                "zone_slug": "aws-us-east-2-1",
                "test_kb_slug": "nuclia-e2e-live",
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
        },
        "zones": [
            {
                "name": "europe-1",
                "zone_slug": "europe-1",
                "test_kb_slug": "nuclia-e2e-live",
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


@pytest.fixture(scope="session")
async def aiohttp_session():
    """
    Create a shared aiohttp session for the entire test session.
    """
    async with aiohttp.ClientSession() as session:
        yield session


@pytest.fixture(scope="session")
def global_api(aiohttp_session):
    """
    Provide a configured GlobalAPI instance for tests.
    """
    global_config = CLUSTERS_CONFIG[TEST_ENV]["global"]
    return GlobalAPI(
        f"https://{global_config['base_url']}",
        global_config["recaptcha"],
        global_config["root_pat_token"],
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
def regional_api_config(request, global_api_config):
    zone_config = deepcopy(request.param)
    auth = get_auth()
    config = get_config()
    auth.set_user_token(global_api_config["permanent_account_owner_pat_token"])
    config.set_default_account(global_api_config["permanent_account_slug"])
    config.set_default_zone(zone_config["zone_slug"])
    zone_config["test_kb_slug"] = "{test_kb_slug}-{name}".format(**zone_config)
    zone_config["permanent_account_slug"] = global_api_config["permanent_account_slug"]
    zone_config["permanent_account_id"] = {a.slug: a.id for a in config.accounts}[
        global_api_config["permanent_account_slug"]
    ]
    return zone_config


# class SDKMethodProxy:
#     def __init__(self, instance, **kwargs):
#         self._instance = instance
#         self._kwargs = kwargs

#     def __getattr__(self, name):
#         # Retrieve the attribute (method) from the wrapped instance
#         attr = getattr(self._instance, name)
#         if callable(attr):
#             # If the attribute is a method, wrap it
#             def wrapper(*args, **kwargs):
#                 print(attr, self._instance, kwargs)
#                 kwargs.update(self._kwargs)
#                 return attr(*args, **kwargs)
#             return wrapper
#         return attr  # Return the attribute as is if it's not callable


# class RegionalSDK:

#     class NucliaKBS(NucliaKBSOriginal):

#         @property
#         def _auth(self):
#             return getattr(self, "_test_auth", None)

#         @_auth.setter
#         def _auth(self, auth):
#             self._test_auth = auth

#     def __init__(self, account: str, zone: str, auth: NucliaAuth):
#         self.zone = zone

#         kbs = self.NucliaKBS()
#         kbs._auth = auth
#         self.kbs = SDKMethodProxy(kbs, zone=zone, account=account)


# @pytest.fixture(scope="function")
# async def regional_sdk(regional_api_config, global_api_config):
#     pat_auth = NucliaAuth()
#     pat_auth._inner_config = Config()
#     pat_auth.set_user_token(global_api_config["permanent_account_owner_pat_token"])

#     wrapped = RegionalSDK(
#         zone=regional_api_config["zone_slug"],
#         account=global_api_config["permanent_account_slug"],
#         auth=pat_auth
#     )
#     print(wrapped, regional_api_config["zone_slug"])
#     yield wrapped

# @pytest.fixture(scope=function)
# def permament_nua_auth():
#     nuclia_auth = NucliaAuth()
#     client_id = nuclia_auth.nua(token.nua_key)
#     assert client_id
#     nuclia_auth._config.set_default_nua(client_id)


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


@pytest.fixture(scope="session")
def email_util():
    return EmailUtil("carles@nuclia.com", "oynpctapnzwqjxol")


@pytest.fixture
async def cleanup_test_account(global_api: GlobalAPI):
    await global_api.manager.delete_account(TEST_ACCOUNT_SLUG)

    yield

    await global_api.manager.delete_account(TEST_ACCOUNT_SLUG)


@pytest.fixture
async def clean_kb_test(request, regional_api_config):
    kbs = NucliaKBS()
    kb_slug = regional_api_config["test_kb_slug"]
    all_kbs = await asyncio.to_thread(partial(kbs.list, zone=regional_api_config["zone_slug"]))
    kb_ids_by_slug = {kb.slug: kb.id for kb in all_kbs}
    kb_id = kb_ids_by_slug.get(kb_slug)
    try:
        await asyncio.to_thread(partial(kbs.delete, zone=regional_api_config["zone_slug"], id=kb_id))
    except ValueError:
        # Raised by sdk when kb not found
        pass


@pytest.fixture
async def nua_client(regional_api_config):
    nc = AsyncNuaClient(
        region=regional_api_config["zone_slug"],
        account=regional_api_config["permanent_account_id"],
        token=regional_api_config["permanent_nua_key"],
    )
    return nc