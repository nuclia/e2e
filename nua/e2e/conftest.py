import logging
import os
import tempfile

import nuclia
import pytest
from nuclia.config import reset_config_file, set_config_file
from nuclia.sdk.auth import NucliaAuth
from dataclasses import dataclass

logger = logging.getLogger("e2e")


@dataclass
class Tokens:
    nua_key: str
    pat_key: str
    account_id: str


STAGE_ACCOUNT_ID = "f2edd58e-431f-4197-be76-6fc611082fe8"
PROD_ACCOUNT_ID = "5cec111b-ea23-4b0c-a82a-d1a666dd1fd2"

TOKENS: dict[str, Tokens] = {
    "europe-1.stashify.cloud": Tokens(
        nua_key=os.environ.get("TEST_EUROPE1_STASHIFY_NUA"),
        pat_key=os.environ.get("STAGE_PERMAMENT_ACCOUNT_OWNER_PAT_TOKEN"),
        account_id=os.environ.get("TEST_EUROPE1_STASHIFY_ACCOUNT", STAGE_ACCOUNT_ID),
    ),
    "europe-1.nuclia.cloud": Tokens(
        nua_key=os.environ.get("TEST_EUROPE1_NUCLIA_NUA"),
        pat_key=os.environ.get("PROD_PERMAMENT_ACCOUNT_OWNER_PAT_TOKEN"),
        account_id=PROD_ACCOUNT_ID,
    ),
    "aws-us-east-2-1.nuclia.cloud": Tokens(
        nua_key=os.environ.get("TEST_AWS_US_EAST_2_1_NUCLIA_NUA"),
        pat_key=os.environ.get("PROD_PERMAMENT_ACCOUNT_OWNER_PAT_TOKEN"),
        account_id=PROD_ACCOUNT_ID,
    ),
}


@pytest.fixture(
    scope="function",
    params=[
        "europe-1.stashify.cloud",
        "europe-1.nuclia.cloud",
        "aws-us-east-2-1.nuclia.cloud",
    ],
)
def nua_config(request):
    if (
        os.environ.get("TEST_ENV") == "stage" and "stashify.cloud" not in request.param  # noqa
    ):  # noqa
        pytest.skip("skipped on this platform: {}")

    nuclia.REGIONAL = f"https://{request.param}"

    token = TOKENS.get(request.param)

    assert token
    assert token.nua_key
    assert token.pat_key
    assert token.account_id

    with tempfile.NamedTemporaryFile() as temp_file:
        temp_file.write(b"{}")
        temp_file.flush()
        set_config_file(temp_file.name)
        nuclia_auth = NucliaAuth()
        client_id = nuclia_auth.nua(token.nua_key)
        assert client_id
        nuclia_auth._config.set_default_nua(client_id)

        yield request.param
        reset_config_file()
