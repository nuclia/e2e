import logging
import os
import tempfile

import nuclia
import pytest
from nuclia.sdk.auth import NucliaAuth
from nuclia.lib.nua import AsyncNuaClient
from dataclasses import dataclass
from typing import AsyncGenerator

logger = logging.getLogger("e2e")


@dataclass
class Tokens:
    nua_key: str
    pat_key: str
    account_id: str


STAGE_ACCOUNT_ID = "f2edd58e-431f-4197-be76-6fc611082fe8"
PROD_ACCOUNT_ID = "5cec111b-ea23-4b0c-a82a-d1a666dd1fd2"

TOKENS: dict[str, Tokens] = {
    "https://europe-1.stashify.cloud": Tokens(
        nua_key=os.environ.get("TEST_EUROPE1_STASHIFY_NUA"),
        pat_key=os.environ.get("STAGE_PERMAMENT_ACCOUNT_OWNER_PAT_TOKEN"),
        account_id=os.environ.get("TEST_EUROPE1_STASHIFY_ACCOUNT", STAGE_ACCOUNT_ID),
    ),
    "https://europe-1.nuclia.cloud": Tokens(
        nua_key=os.environ.get("TEST_EUROPE1_NUCLIA_NUA"),
        pat_key=os.environ.get("PROD_PERMAMENT_ACCOUNT_OWNER_PAT_TOKEN"),
        account_id=PROD_ACCOUNT_ID,
    ),
    "https://aws-us-east-2-1.nuclia.cloud": Tokens(
        nua_key=os.environ.get("TEST_AWS_US_EAST_2_1_NUCLIA_NUA"),
        pat_key=os.environ.get("PROD_PERMAMENT_ACCOUNT_OWNER_PAT_TOKEN"),
        account_id=PROD_ACCOUNT_ID,
    ),
}


@pytest.fixture(
    scope="function",
    params=[
        "https://europe-1.stashify.cloud",
        "https://europe-1.nuclia.cloud",
        "https://aws-us-east-2-1.nuclia.cloud",
    ],
)
async def nua_config(request) -> AsyncGenerator[AsyncNuaClient, None]:
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

    yield AsyncNuaClient(
        region=request.param, account=token.account_id, token=token.nua_key
    )
