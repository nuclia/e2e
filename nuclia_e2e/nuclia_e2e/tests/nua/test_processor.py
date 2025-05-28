from nuclia.lib.nua import AsyncNuaClient
from nuclia.sdk.process import AsyncNucliaProcessing
from nuclia_e2e.utils import get_asset_file_path

import pytest
import asyncio


#
# NOTE
#
# Scheduling timeouts are set so that we have more clear errors, and we don't mix together a failure
# caused by a slow processor with a slow scheduling, just to reduce noise when debugging.
#
# wait for processing Timeouts are set to +50% of the experienced elapsed processing time during test
# setup, plus an exta margin seconds to account for any first processor container execution stuff
# like loading some models, that some times takes up to 120 seconds
#

EXTRA_PROCESSING_TIME_MARGIN = 120
EXTRA_PROCESSING_TIME_FACTOR = 1.5


async def wait_for_scheduling(processing_id: str, client: AsyncNuaClient, timeout: int = 200):
    count = timeout
    status = await client.processing_id_status(processing_id)
    while status.scheduled is False and count > 0:
        status = await client.processing_id_status(processing_id)
        await asyncio.sleep(1)
        count -= 1
    # don't wait for finishing if has not been scheduled on time
    return status.scheduled


@pytest.mark.asyncio_cooperative
async def test_pdf(request: pytest.FixtureRequest, nua_client: AsyncNuaClient):
    path = get_asset_file_path("2310.14587.pdf")

    response = await nua_client.process_file(path, "kbid")
    print(f"{request.node.name} ::: Processing_id = {response.processing_id}")
    scheduled = await wait_for_scheduling(response.processing_id, nua_client)
    assert scheduled, f"processing_id = {response.processing_id} was not scheduled in time"

    expected_processing_time = int(120 * EXTRA_PROCESSING_TIME_FACTOR)
    payload = await nua_client.wait_for_processing(
        response, timeout=expected_processing_time + EXTRA_PROCESSING_TIME_MARGIN
    )

    assert payload, f"processing_id = {response.processing_id} did not finish processing in time"
    assert "As the training data of LLMs often contains undesirable" in payload.extracted_text[0].body.text


@pytest.mark.asyncio_cooperative
async def test_video(request: pytest.FixtureRequest, nua_client: AsyncNuaClient):
    path = get_asset_file_path("simple_video.mp4")

    response = await nua_client.process_file(path, "kbid")
    print(f"{request.node.name} ::: Processing_id = {response.processing_id}")
    scheduled = await wait_for_scheduling(response.processing_id, nua_client)
    assert scheduled, f"processing_id = {response.processing_id} was not scheduled in time"

    expected_processing_time = int(90 * EXTRA_PROCESSING_TIME_FACTOR)
    payload = await nua_client.wait_for_processing(
        response, timeout=expected_processing_time + EXTRA_PROCESSING_TIME_MARGIN
    )

    assert payload, f"processing_id = {response.processing_id} did not finish processing in time"
    assert "This is one of the most reflective mirrors" in payload.extracted_text[0].body.text


@pytest.mark.asyncio_cooperative
async def test_vude_1(request: pytest.FixtureRequest, nua_client: AsyncNuaClient):
    path = get_asset_file_path("y2mate_is_Stone_1_Minute_Short_Film_Hot_Shot_5hPtU8Jbpg0_720p_1701938639.mp4")

    response = await nua_client.process_file(path, "kbid")
    print(f"{request.node.name} ::: Processing_id = {response.processing_id}")
    scheduled = await wait_for_scheduling(response.processing_id, nua_client)
    assert scheduled, f"processing_id = {response.processing_id} was not scheduled in time"

    expected_processing_time = int(44 * EXTRA_PROCESSING_TIME_FACTOR)
    payload = await nua_client.wait_for_processing(
        response, timeout=expected_processing_time + EXTRA_PROCESSING_TIME_MARGIN
    )

    assert payload, f"processing_id = {response.processing_id} did not finish processing in time"
    assert "harmful" in payload.extracted_text[0].body.text


@pytest.mark.asyncio_cooperative
async def test_activity(nua_client: AsyncNuaClient):
    nc = AsyncNucliaProcessing()
    await nc.status(nc=nua_client)


@pytest.mark.asyncio_cooperative
async def test_pptx(request: pytest.FixtureRequest, nua_client: AsyncNuaClient):
    path = get_asset_file_path("test_slides.pptx")

    response = await nua_client.process_file(path, "kbid")
    print(f"{request.node.name} ::: Processing_id = {response.processing_id}")
    scheduled = await wait_for_scheduling(response.processing_id, nua_client)
    assert scheduled, f"processing_id = {response.processing_id} was not scheduled in time"

    expected_processing_time = int(26 * EXTRA_PROCESSING_TIME_FACTOR)
    payload = await nua_client.wait_for_processing(
        response, timeout=expected_processing_time + EXTRA_PROCESSING_TIME_MARGIN
    )

    assert payload, f"processing_id = {response.processing_id} did not finish processing in time"
    assert "This is a test ppt" in payload.extracted_text[0].body.text


@pytest.mark.asyncio_cooperative
async def test_manual_split(request: pytest.FixtureRequest, nua_client: AsyncNuaClient):
    path = get_asset_file_path("plaintext_manual_split.txt")

    response = await nua_client.process_file(path, "kbid")
    print(f"{request.node.name} ::: Processing_id = {response.processing_id}")
    scheduled = await wait_for_scheduling(response.processing_id, nua_client)
    assert scheduled, f"processing_id = {response.processing_id} was not scheduled in time"

    expected_processing_time = int(30 * EXTRA_PROCESSING_TIME_FACTOR)
    payload = await nua_client.wait_for_processing(
        response, timeout=expected_processing_time + EXTRA_PROCESSING_TIME_MARGIN
    )

    assert payload, f"processing_id = {response.processing_id} did not finish processing in time"
    assert len(payload.field_metadata[0].metadata.metadata.paragraphs) == 11
