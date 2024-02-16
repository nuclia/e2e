from pathlib import Path
from nuclia.sdk.process import NucliaProcessing
import pytest

FILE_PATH = f"{Path(__file__).parent.parent}/assets/"


def define_path(file: str):
    return FILE_PATH + file


@pytest.mark.timeout(360)
def test_pdf(nua_config):
    path = define_path("2310.14587.pdf")
    nc = NucliaProcessing()
    payload = nc.process_file(path, kbid="kbid", timeout=200)
    assert payload
    assert (
        "As the training data of LLMs often contains undesirable"
        in payload.extracted_text[0].body.text
    )


@pytest.mark.timeout(360)
def test_video(nua_config):
    path = define_path("simple_video.mp4")
    nc = NucliaProcessing()
    payload = nc.process_file(path, kbid="kbid", timeout=200)
    assert payload
    assert (
        "This is one of the most reflective mirrors"
        in payload.extracted_text[0].body.text
    )


@pytest.mark.timeout(360)
def test_vude_1(nua_config):
    path = define_path(
        "y2mate_is_Stone_1_Minute_Short_Film_Hot_Shot_5hPtU8Jbpg0_720p_1701938639.mp4"  # noqa
    )
    nc = NucliaProcessing()
    payload = nc.process_file(path, kbid="kbid", timeout=200)
    assert payload
    print(payload.extracted_text[0].body)
    assert "harmful" in payload.extracted_text[0].body.text


@pytest.mark.timeout(360)
def test_vude_2(nua_config):
    path = define_path(
        "yt5s.io-The Wait  - 1 Minute Short Film _ Award Winning.mp4"
    )  # noqa
    nc = NucliaProcessing()
    payload = nc.process_file(path, kbid="kbid", timeout=200)
    assert payload
    print(payload.extracted_text[0].body)
    assert "two months" in payload.extracted_text[0].body.text


def test_activity(nua_config):
    nc = NucliaProcessing()
    nc.status()
