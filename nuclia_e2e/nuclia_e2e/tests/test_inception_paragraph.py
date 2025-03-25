from functools import wraps
from nuclia.data import get_auth
from nuclia.sdk.kb import AsyncNucliaKB
from nuclia_e2e.tests.conftest import ZoneConfig
from nuclia_e2e.utils import get_asset_file_path
from nuclia_e2e.utils import get_async_kb_ndb_client
from nuclia_e2e.utils import wait_for
from nucliadb_models.common import Paragraph
from nucliadb_models.metadata import ResourceProcessingStatus
from nucliadb_sdk.v2.exceptions import NotFoundError
from typing import Any

import pytest


@pytest.mark.asyncio_cooperative
async def test_inception_paragraph_type_is_generated(regional_api_config: ZoneConfig):
    kb_id = regional_api_config.permanent_kb_id
    zone = regional_api_config.zone_slug

    auth = get_auth()
    async_ndb = get_async_kb_ndb_client(zone=zone, kbid=kb_id, user_token=auth._config.token)
    kb = AsyncNucliaKB()

    resource_slug = "inception-e2e-test-safe-to-remove"
    try:
        await kb.resource.delete(slug=resource_slug, ndb=async_ndb)
    except NotFoundError:
        pass

    rid = await kb.resource.create(
        title="E2E test inception paragraph (Safe to remove)",
        slug=resource_slug,
        ndb=async_ndb,
    )
    await kb.upload.file(
        rid=rid, path=get_asset_file_path(file="test-image.pdf"), field="file", ndb=async_ndb
    )

    # Wait for resource to be processed
    def resource_is_processed(rid):
        @wraps(resource_is_processed)
        async def condition() -> tuple[bool, Any]:
            resource = await kb.resource.get(rid=rid, ndb=async_ndb)
            return (
                resource.metadata.status == ResourceProcessingStatus.PROCESSED,
                None,
            )

        return condition

    success, _ = await wait_for(resource_is_processed(rid))
    assert success, "File was not processed in time, PROCESSED status not found in resource"

    resource = await kb.resource.get(rid=rid, ndb=async_ndb, show="extracted")
    assert "cat" in resource.data.files["file"].extracted.text.text
    paragraph = [
        p
        for p in resource.data.files["file"].extracted.metadata.metadata.paragraphs
        if p.kind == Paragraph.TypeParagraph.INCEPTION
    ]
    assert len(paragraph) == 1
    await kb.resource.delete(rid=rid, ndb=async_ndb)
