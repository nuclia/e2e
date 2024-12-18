import pytest
from nuclia.sdk.process import AsyncNucliaProcessing
from regional.utils import define_path


@pytest.mark.asyncio_cooperative
@pytest.mark.timeout(660)
async def test_pdf(nua_config):
    path = define_path("2310.14587.pdf")
    nc = AsyncNucliaProcessing()
    payload = await nc.process_file(path, kbid="kbid", timeout=300)
    assert payload
    assert (
        "As the training data of LLMs often contains undesirable"
        in payload.extracted_text[0].body.text
    )


@pytest.mark.asyncio_cooperative
@pytest.mark.timeout(360)
async def test_video(nua_config):
    path = define_path("simple_video.mp4")
    nc = AsyncNucliaProcessing()
    payload = await nc.process_file(path, kbid="kbid", timeout=300)
    assert payload
    assert (
        "This is one of the most reflective mirrors"
        in payload.extracted_text[0].body.text
    )


@pytest.mark.asyncio_cooperative
@pytest.mark.timeout(660)
async def test_vude_1(nua_config):
    path = define_path(
        "y2mate_is_Stone_1_Minute_Short_Film_Hot_Shot_5hPtU8Jbpg0_720p_1701938639.mp4"  # noqa
    )
    nc = AsyncNucliaProcessing()
    payload = await nc.process_file(path, kbid="kbid", timeout=300)
    assert payload
    print(payload.extracted_text[0].body)
    assert "harmful" in payload.extracted_text[0].body.text


@pytest.mark.asyncio_cooperative
async def test_activity(nua_config):
    nc = AsyncNucliaProcessing()
    await nc.status()
