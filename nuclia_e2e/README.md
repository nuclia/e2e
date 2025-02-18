# Nuclia E2E Tests

This document describes the **end-to-end (E2E) test suite** for Nuclia at the API level. It outlines **how** these tests are written, **why** certain tests are included, and the **guidelines** for contributors looking to add or modify tests.

--

## Scope and Purpose

- **Black-box, API-level tests**: We call publicly accessible (or documented) Nuclia endpoints and verify real responses.
- **No mocking**: Tests run against actual Nuclia services and external dependencies (e.g., Stripe, LLMs).
- **Not for edge cases**: Edge cases and heavy parametrization belong in CI/unit tests unless an external dependency is involved.
- **‘Eat Our Own Dog Food’**: Whenever possible, tests use the official Nuclia SDK to ensure we detect issues in our own libraries before our customers do. If there's something missing in the SDK, and make sense that is there, please add it.

---

## Guidelines for e2e tests

1. **When to add tests**
   - Add an e2e if the feature or endpoint interacts with an external service
   - Add an e2e if the feature or endpoint depends on another nuclia service
   - Add an e2e to test a complex workflow that involves several interactions with the api
   - Aim to ensure every significant Nuclia endpoint is covered at least once with the "happy path"

2. **Use the SDK Wherever Possible**
   - If a public endpoint is missing async or sync methods, consider adding it to the SDK.
   - If an endpoint is undocumented or not meant to be in the SDK (e.g., management or dataset endpoints), add it to a fixture-based HTTP client.

2. **Avoid Exhaustive Parametrization**
   - Do not re-check every possible scenario in E2E tests, that should be part of CI coverage.
   - Only include detailed cases in E2E if an external integration (e.g., payment, LLM calls) requires verification in a production-like environment.

3. **Meaningful Assertions**
   - Provide clear assertions and error messages to make failures easy to diagnose: this is specially important to avoid losing time chasing false positives.

4. **Minimize External Costs**
   - Some services (like LLMs) can be expensive. Test only what’s necessary to validate the functionality, and use only the cheapest model when possibe.

---

## Authentication in Tests

There are different ways to authenticate to the services, each one will be used where it makes sense, here's a summary of what is available.

### Global Authentication
- **OAuth token**: Acquired through the standard Nuclia login endpoint. Fixtures already use a preshared recaptcha bypass token to make this possible. This should be used only when for some reason we need to validate something related with a recently issued token.
- **Pre-generated Personal Access Token (PAT)**: For instance, `PROD_PERMANENT_ACCOUNT_OWNER_PAT_TOKEN` or `STAGE_PERMANENT_ACCOUNT_OWNER_PAT_TOKEN` are used in several fixtures.

### Regional Authentication
- **Pre-generated PAT**: Specific to a test user within a particular region.
- **Service account**: For `/api/v1/kb`-scoped API usage.
- **NUA key**: For the “NUA API,” i.e., any regional endpoint outside `/api/v1/kb*` or `/api/v1/account^` namespaces.

---

## Test assets

There are a handful of Users, Accounts, and KBs pregenerated that these tests use, so it's important to be aware of them to avoid altering or deleting, to ensure tests work as intended.

1. **Account**
   - All tests run under the `automated-testing` account, available on both `nuclia.cloud` and `stashify.cloud`.

2. **Users**
   - **Nuclia E2E Tests Owner**
     - Email: `testing_sdk@nuclia.com` (redirects to a mailing list, you can't login with it on a gmail inbox).
     - Pre-generated PAT tokens: `PROD_PERMANENT_ACCOUNT_OWNER_PAT_TOKEN` and `STAGE_PERMANENT_ACCOUNT_OWNER_PAT_TOKEN`.
   - **Nuclia E2E Root**
     - Email: `testing_sdk+root@nuclia.com`.
     - Has pre-generated PAT tokens: `PROD_ROOT_PAT_TOKEN` and `STAGE_ROOT_PAT_TOKEN`.
     - **Caution**: This user can delete accounts by slug. Only use if owner-level PATs are insufficient.
   - **Account nua tokens**: `TEST_{ZONE}_NUCLIA_NUA`

3. **Pre-Existing Knowledge Boxes (KBs)**
   - `pre-existing-kb`: Used by betterstack external monitors on all regions; by these tests.
     - in this kb there are two resources "omelette" and "roasted-chicken" setup to validate security groups.
     - in this kb you may see a service account named "test-e2e-kb-auth", that is dynamically created by the e2e.
   - `nuclia-e2e-live-{region}`: Dynamically created KBs for tests. They are cleaned up automatically, and the slug is reused.
   - `base-e2e` (stage only): A source of exports for certain tests. **Do not modify or delete** if you don't now what you are doing.

---

## Test Implementation Details

###  Location and naming
- There's not any specific naming convention (yet) so try to avoid overclassification at this point. Add your tests in any existing `test_*.py` file in the root, or create one. Try to name it referencing the feature(s) it tests.
- Nua tests copied from the old nua tests live in it's own `tests/nua` folder.
-
### Concurrency
Tests use `pytest` with a plugin called `pytest-asyncio-cooperative`. This is different of just allowing async tests like in our usual `pytest-asyncio` tests, as here **all tests run concurrently** (default limit: 100 tasks). This drastically shortens overall runtime by overlapping waiting time, as the whole test suite duration approximates to the longer test duration.

If at some point we hit concurrency issues, we can limit this with `--max-asyncio-tasks`. Also, even if the concurrency is a big win here in terms of total test duration, any test that uses code that has any "bad" asyncio code, will make the tests run slower and eventually fall because of timeouts or connection errors. To name just a few of the usual culprits:
 - time.sleep inside an async function
 - running cpu-bound code on async function
 - long requests without enough yields (e.g upload operations without streaming)

 Aside of this, as we suspect (not 100% sure) that there are asyncio related issues that causes some timeuts (httpx  ReadTimeout and ConnectTimeout mostly), we ended up using `pytest-shard` so all tests are splitted into 3 different pytest instances.


### Configuration
- All needd config defined in `conftest.py` under `CLUSTERS_CONFIG`, secrets loaded from GHA injected env vars.
- Each environment (`prod` and `stage` currently) can define several zones, and will be run in a separate action. Anything you need to add, make sure you add it in all environments.
- Each action will run tests for all the zones defined in that environment.
- `regional_api_config` fixture provides environment + region details for region-scoped tests and triggers the parametrization so tests with this fixture runs once for each region.
- `global_api_config`: Provides environment details for global tests, no parametrization here.

### SDK usage in Tests

The Nuclia SDK is implemented as a singleton in terms of how it handles the configuration, which was causing overwrites when running tests concurrently, to work around some issues caused by that we did several things:
- We **inject** a `NucliaDBClient` or `NuaClient` fixture into each test function using the `nc` and `ndb` parameters of sdk methods. These clients are available as fixtures or instantiated directly in the test code if needed.
- On conftest.py, we patch httpx to be able to provide a higher timeout for all clients created within the e2e

--

## TODO
- **Minimum Endpoint Coverage**: Confirm that all documented public endpoints appear in at least one E2E test.
- **Feature Checklist** : Maintain an up-to-date list of features, noting whether they have E2E coverage and why.
