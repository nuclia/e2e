from nuclia.lib.nua import AsyncNuaClient
from nuclia.sdk.process import AsyncNucliaProcessing
from nuclia_e2e.utils import get_asset_file_path

import pytest


@pytest.mark.asyncio_cooperative
@pytest.mark.timeout(660)
async def test_pdf(nua_client: AsyncNuaClient):
    path = get_asset_file_path("2310.14587.pdf")
    nc = AsyncNucliaProcessing()
    payload = await nc.process_file(path, kbid="kbid", timeout=300, nc=nua_client)
    assert payload
    assert "As the training data of LLMs often contains undesirable" in payload.extracted_text[0].body.text


@pytest.mark.asyncio_cooperative
@pytest.mark.timeout(360)
async def test_video(nua_client: AsyncNuaClient):
    path = get_asset_file_path("simple_video.mp4")
    nc = AsyncNucliaProcessing()
    payload = await nc.process_file(path, kbid="kbid", timeout=300, nc=nua_client)
    assert payload
    assert "This is one of the most reflective mirrors" in payload.extracted_text[0].body.text


@pytest.mark.asyncio_cooperative
@pytest.mark.timeout(660)
async def test_vude_1(nua_client: AsyncNuaClient):
    path = get_asset_file_path("y2mate_is_Stone_1_Minute_Short_Film_Hot_Shot_5hPtU8Jbpg0_720p_1701938639.mp4")
    nc = AsyncNucliaProcessing()
    payload = await nc.process_file(path, kbid="kbid", timeout=300, nc=nua_client)
    assert payload
    assert "harmful" in payload.extracted_text[0].body.text


@pytest.mark.asyncio_cooperative
async def test_activity(nua_client: AsyncNuaClient):
    nc = AsyncNucliaProcessing()
    await nc.status(nc=nua_client)


@pytest.mark.asyncio_cooperative
async def test_pptx(nua_client: AsyncNuaClient):
    path = get_asset_file_path("test_slides.pptx")
    nc = AsyncNucliaProcessing()
    payload = await nc.process_file(path, kbid="kbid", timeout=300, nc=nua_client)
    assert payload
    assert "This is a test ppt" in payload.extracted_text[0].body.text


@pytest.mark.asyncio_cooperative
async def test_manual_split(nua_client: AsyncNuaClient):
    nc = AsyncNucliaProcessing()
    path = get_asset_file_path("plaintext_manual_split.txt")
    payload = await nc.process_file(path, kbid="kbid", timeout=300, nc=nua_client)
    assert payload
    assert len(payload.field_metadata[0].metadata.metadata.paragraphs) == 11
