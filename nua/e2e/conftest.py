import os
import tempfile

import pytest

import nuclia
from nuclia.config import reset_config_file, set_config_file
from nuclia.sdk import NucliaAuth

import logging

logger = logging.getLogger("e2e")


TOKENS = {
    "europe-1.stashify.cloud": os.environ.get("TEST_EUROPE1_STASHIFY_NUA"),
    "europe-1.nuclia.cloud": os.environ.get("TEST_EUROPE1_NUCLIA_NUA"),
    "aws-us-east-2-1.nuclia.cloud": os.environ.get("TEST_AWS_US_EAST_2_1_NUCLIA_NUA"),
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
        os.environ.get("TEST_ENV") == "stage"
        and "stashify.cloud" not in request.param  # noqa
    ):  # noqa
        pytest.skip("skipped on this platform: {}")

    nuclia.REGIONAL = f"https://{request.param}"

    token = TOKENS.get(request.param)

    assert token

    with tempfile.NamedTemporaryFile() as temp_file:
        temp_file.write(b"{}")
        temp_file.flush()
        set_config_file(temp_file.name)
        nuclia_auth = NucliaAuth()
        client_id = nuclia_auth.nua(token)
        assert client_id
        nuclia_auth._config.set_default_nua(client_id)

        yield
        reset_config_file()
