import os
import requests
import pytest
import random
import string

import imaplib
import email
import re
import time
from email.header import decode_header
import tempfile
from nuclia.config import reset_config_file, set_config_file
from nuclia.data import get_auth
from nuclia.data import get_config
import nuclia
from nuclia.sdk.auth import NucliaAuth
from nuclia.sdk.kbs import NucliaKBS
from copy import deepcopy


# All tests that needs some existing account will use the one configured in the global "permanent_account_slug"
# with some predefined user credentials without expiration:
# "permanent_account_owner_pat": PAT token for `testing_sdk@nuclia.com` on the suitable account

CLUSTERS_CONFIG = {
    "prod": {
        "global": {
            "base_url": "https://nuclia.cloud",
            "recaptcha": os.environ.get("PROD_GLOBAL_RECAPTCHA"),
            "root_pat_token": os.environ.get("PROD_ROOT_PAT_TOKEN"),
            "permanent_account_slug": "automated-testing",
            "permanent_account_owner_pat_token": os.environ.get("PROD_PERMAMENT_ACCOUNT_OWNER_PAT_TOKEN")
        },
        "zones": [
            {
                "name": "aws-us-east-2-1",
                "zone_slug": "aws-us-east-2-1",
                "base_url": "https://aws-us-east-2-1.nuclia.cloud",
                "test_kb_slug": "nuclia-e2e-live-aws-us-east-2-1"
            },
            {
                "name": "europe-1",
                "zone_slug": "europe-1",
                "base_url": "https://europe-1.nuclia.cloud",
                "test_kb_slug": "nuclia-e2e-live-europe-1"
            },
        ]
    },
    "stage": {
        "global": {
            "base_url": "https://stashify.cloud",
            "recaptcha": os.environ.get("STAGE_GLOBAL_RECAPTCHA"),
            "root_pat_token": os.environ.get("STAGE_ROOT_PAT_TOKEN"),
            "permanent_account_slug": "automated-testing",
            "permanent_account_owner_pat_token": os.environ.get("STAGE_PERMAMENT_ACCOUNT_OWNER_PAT_TOKEN")
        },
        "zones": [
            {
                "name": "europe-1",
                "zone_slug": "europe-1",
                "base_url": "https://europe-1.stashify.cloud",
                "test_kb_slug": "nuclia-e2e-live"

            },
            # uncomment to test two zone parallel testing on stage
            # {
            #     "name": "europe-2",
            #     "zone_slug": "europe-1",
            #     "base_url": "https://europe-1.stashify.cloud",
            #     "test_kb_slug": "nuclia-e2e-live"
            # }

        ]
    }
}
TEST_ACCOUNT_SLUG = "test-e2e-creation"
TEST_ENV = os.environ.get("TEST_ENV")
TEST_ONBOARD_INQUIRY = {
    "company": "Nuclia e2e",
    "use_case": "Other",
    "role": "Other",
    "organization_size": "1-50",
    "phone": "+34 111 222 333",
    "receive_updates": False
}


@pytest.fixture(scope="session")
def test_config():
    return {
        "test_account_slug": TEST_ACCOUNT_SLUG
    }


class ManagerAPI:
    def __init__(self, global_api):
        self.global_api = global_api
        self.session = requests.Session()

    def delete_account(self, account_slug) -> bool:
        url = f"{self.global_api.base_url}/api/manage/@account/{account_slug}"
        response = self.session.delete(url, headers=self.global_api.root_auth_headers)
        if response.status_code not in (204, 404):
            response.raise_for_status()
        return response.status_code == 204

class GlobalAPI:
    def __init__(self, base_url, recaptcha, root_pat_token):
        self.base_url = base_url
        self.session = requests.Session()
        self.recaptcha = recaptcha
        self.access_token = None
        self.root_pat_token = root_pat_token
        self.manager = ManagerAPI(self)

    @property
    def auth_headers(self):
        headers = {
            'Authorization': f'Bearer {self.access_token}',
        }
        return headers

    @property
    def root_auth_headers(self):
        headers = {
            'Authorization': f'Bearer {self.root_pat_token}',
        }
        return headers

    def signup(self, name, email, password):
        url = f"{self.base_url}/api/auth/signup"
        payload = {
            "name": name,
            "email": email,
            "password": password
        }
        headers = {
            'X-STF-VALIDATION': self.recaptcha
        }
        response = self.session.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

    def finalize_signup(self, signup_token):
        url = f"{self.base_url}/api/auth/magic?token={signup_token}"
        response = self.session.post(url)
        response.raise_for_status()
        return response.json()

    def set_access_token(self, access_token):
        self.access_token = access_token

    def send_onboard_inquiry(self, data=TEST_ONBOARD_INQUIRY):
        url = f"{self.base_url}/api/v1/user/onboarding_inquiry"
        response = self.session.put(url, json=data, headers=self.auth_headers)
        response.raise_for_status()

    def create_account(self, slug):
        if not self.access_token:
            raise ValueError("Access token is not set. Please provide an access token.")
        url = f"{self.base_url}/api/v1/accounts"
        response = self.session.post(url, json={"slug": slug, "title": slug}, headers=self.auth_headers)
        response.raise_for_status()
        return response.json()["id"]


@pytest.fixture(scope="function")
def global_api():
    global_config = CLUSTERS_CONFIG[TEST_ENV]["global"]
    return GlobalAPI(global_config["base_url"], global_config["recaptcha"], global_config["root_pat_token"])


@pytest.fixture(scope="function")
def global_api_config():
    global_config = CLUSTERS_CONFIG[TEST_ENV]["global"]
    nuclia.BASE = global_config["base_url"]
    os.environ["TESTING"] = "True"
    with tempfile.NamedTemporaryFile() as temp_file:
        temp_file.write(b"{}")
        temp_file.flush()
        set_config_file(temp_file.name)
        yield global_config
        reset_config_file()


@pytest.fixture(scope="function", params=list(CLUSTERS_CONFIG[TEST_ENV]["zones"]))
def regional_api_config(request, global_api_config):
    zone_config = deepcopy(request.param)
    nuclia.REGIONAL = zone_config["base_url"]
    auth = get_auth()
    config = get_config()
    auth.set_user_token(global_api_config["permanent_account_owner_pat_token"])
    config.set_default_account(global_api_config["permanent_account_slug"])
    config.set_default_zone(zone_config["zone_slug"])
    zone_config["test_kb_slug"] = '{test_kb_slug}-{name}'.format(**zone_config)
    yield zone_config

class EmailUtil:
    def __init__(self, base_address, gmail_app_password):
        self.base_address = base_address
        self.gmail_app_password = gmail_app_password

    def generate_email_address(self):
        user, domain = self.base_address.split('@')
        random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=8)).lower()
        return f"{user}++testing++{random_string}@{domain}"

    def get_last_email_body(self, test_address):
        """
        Retrieves the HTML content of the last email sent to the specified test address.
        """
        # Connect to Gmail
        imap_host = 'imap.gmail.com'
        username = self.base_address
        password = self.gmail_app_password

        mail = imaplib.IMAP4_SSL(imap_host)
        mail.login(username, password)
        mail.select('inbox')

        # Search for emails targeted to the specific email variant
        status, messages = mail.search(None, 'TO', f'"{test_address}"')
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
                else:
                    # For non-multipart emails
                    if msg.get_content_type() == "text/html":
                        html_content = msg.get_payload(decode=True).decode()

                mail.logout()
                return html_content
        try:
            mail.logout()
        except Exception:
            return None

    def wait_for_email_signup_link(self, email_address, max_wait_time=20):
        print(f"waiting 10 seconds for signup email at {email_address}")
        signup_url = None
        for i in range(max_wait_time):
            print("still waiting...")
            time.sleep(1)
            body = self.get_last_email_body(email_address)
            if body:
                # Find URLs containing "ls/click". This is to identify sendgrid "wrapping" for click tracking
                urls = re.findall(r"(https?://.*?ls/click.*?['\"])", body)
                if urls:
                    signup_url = urls[0].rstrip('"').rstrip("'")
                return signup_url
        return signup_url

@pytest.fixture(scope="session")
def email_util():
    util = EmailUtil("carles@nuclia.com", "oynpctapnzwqjxol")
    return util


@pytest.fixture(scope="function")
def cleanup_test_account(global_api: GlobalAPI):
    global_api.manager.delete_account(TEST_ACCOUNT_SLUG)

    yield

    global_api.manager.delete_account(TEST_ACCOUNT_SLUG)


@pytest.fixture(scope="function")
def clean_kb_test(request, regional_api_config):
    kbs = NucliaKBS()
    try:
        kbs.delete(slug=regional_api_config["test_kb_slug"])
    except ValueError:
        # Raised by sdk when kb not found
        pass

    yield
