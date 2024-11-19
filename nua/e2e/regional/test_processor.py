from pathlib import Path

import pytest
from nuclia.sdk.process import NucliaProcessing
from nuclia.lib.nua import NuaClient

from nuclia.data import get_auth

FILE_PATH = f"{Path(__file__).parent.parent}/assets/"


def define_path(file: str):
    return FILE_PATH + file


@pytest.mark.timeout(660)
def test_pdf(nua_config):
    path = define_path("2310.14587.pdf")
    nc = NucliaProcessing()
    payload = nc.process_file(path, kbid="kbid", timeout=300)
    assert payload
    assert (
        "As the training data of LLMs often contains undesirable"
        in payload.extracted_text[0].body.text
    )


@pytest.mark.timeout(660)
def test_pptx(nua_config):
    nc = NucliaProcessing()
    path = define_path("sample.pptx")
    payload = nc.process_file(path, kbid="kbid", timeout=300)
    assert payload
    assert "This is a test ppt" in payload.extracted_text[0].body.text


@pytest.mark.timeout(660)
def test_manual_split(nua_config):
    auth = get_auth()
    nua_id = auth._config.get_default_nua()
    nua_obj = auth._config.get_nua(nua_id)
    nc = NuaClient(region=nua_obj.region, account=nua_obj.account, token=nua_obj.token)
    path = define_path("plaintext_manual_split.txt")
    payload = nc.process_file(path, kbid="kbid", timeout=300)
    assert payload
    # TODO: Check extracted paragraphs


@pytest.mark.timeout(360)
def test_video(nua_config):
    path = define_path("simple_video.mp4")
    nc = NucliaProcessing()
    payload = nc.process_file(path, kbid="kbid", timeout=300)
    assert payload
    assert (
        "This is one of the most reflective mirrors"
        in payload.extracted_text[0].body.text
    )


@pytest.mark.timeout(660)
def test_vude_1(nua_config):
    path = define_path(
        "y2mate_is_Stone_1_Minute_Short_Film_Hot_Shot_5hPtU8Jbpg0_720p_1701938639.mp4"  # noqa
    )
    nc = NucliaProcessing()
    payload = nc.process_file(path, kbid="kbid", timeout=300)
    assert payload
    print(payload.extracted_text[0].body)
    assert "harmful" in payload.extracted_text[0].body.text


def test_activity(nua_config):
    nc = NucliaProcessing()
    nc.status()
