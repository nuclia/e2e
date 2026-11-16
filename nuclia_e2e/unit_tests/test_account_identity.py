from nuclia.config import Account
from nuclia_e2e.utils import create_test_kb
from nuclia_e2e.utils import delete_test_agent
from nuclia_e2e.utils import delete_test_kb
from nuclia_e2e.utils import get_agent_from_slug
from nuclia_e2e.utils import get_kbid_from_slug
from nuclia_e2e.utils import require_test_account
from types import SimpleNamespace
from unittest.mock import AsyncMock

import asyncio
import pytest

ACCOUNT_ID = "8c7db65c-3b7e-4140-8165-d37bb4e6e9b8"


@pytest.mark.parametrize("slug", ["automated-testing", "renamed-testing", None])
def test_select_account_by_id(slug: str | None):
    expected = Account(id=ACCOUNT_ID, title="E2E", slug=slug)
    other = Account(id="other-account", title="Other", slug="automated-testing")

    assert require_test_account([other, expected], ACCOUNT_ID, "prod") is expected


@pytest.mark.parametrize("accounts", [[], [Account(id="other-account", title="Other")]])
def test_missing_account_fails_explicitly(accounts: list[Account]):
    with pytest.raises(ValueError, match=f"'{ACCOUNT_ID}'.*'prod'"):
        require_test_account(accounts, ACCOUNT_ID, "prod")


@pytest.fixture
def regional_config():
    return SimpleNamespace(
        zone_slug="europe-1",
        global_config=SimpleNamespace(permanent_account_id=ACCOUNT_ID),
    )


@pytest.mark.parametrize(("helper", "method"), [(get_kbid_from_slug, "kbs"), (get_agent_from_slug, "agents")])
def test_asset_lookup_is_scoped_to_account_and_zone(
    monkeypatch: pytest.MonkeyPatch, regional_config, helper, method: str
):
    assets = [
        SimpleNamespace(id="other-id", slug="other-slug"),
        SimpleNamespace(id="expected-id", slug="test-asset"),
    ]
    lookup = AsyncMock(return_value=assets)
    auth = SimpleNamespace(**{method: lookup})
    monkeypatch.setattr("nuclia_e2e.utils.get_async_auth", lambda: auth)

    assert asyncio.run(helper(regional_config, "test-asset")) == "expected-id"
    lookup.assert_awaited_once_with(ACCOUNT_ID, zone="europe-1", cached=False)


def test_kb_creation_uses_account_id(monkeypatch: pytest.MonkeyPatch, regional_config):
    kbs = SimpleNamespace(add=AsyncMock(return_value={"id": "new-kb"}))
    lookup = AsyncMock(return_value="new-kb")
    monkeypatch.setattr("nuclia_e2e.utils.AsyncNucliaKBS", lambda: kbs)
    monkeypatch.setattr("nuclia_e2e.utils.get_kbid_from_slug", lookup)

    assert asyncio.run(create_test_kb(regional_config, "test-kb", logger=lambda _: None)) == "new-kb"
    kbs.add.assert_awaited_once_with(
        account_id=ACCOUNT_ID,
        zone="europe-1",
        slug="test-kb",
        learning_configuration=None,
    )
    lookup.assert_awaited_once_with(regional_config, "test-kb")


@pytest.mark.parametrize("helper", [delete_test_kb, delete_test_agent])
def test_cleanup_uses_account_id(monkeypatch: pytest.MonkeyPatch, regional_config, helper):
    kbs = SimpleNamespace(delete=AsyncMock())
    monkeypatch.setattr("nuclia_e2e.utils.AsyncNucliaKBS", lambda: kbs)
    monkeypatch.setattr("nuclia_e2e.utils.get_kbid_from_slug", AsyncMock(return_value=None))

    asyncio.run(helper(regional_config, "asset-id", "test-asset", logger=lambda _: None))
    kbs.delete.assert_awaited_once_with(zone="europe-1", id="asset-id", account_id=ACCOUNT_ID)
