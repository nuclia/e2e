# Cloud Storage Sync E2E Tests

## Accounts

- **Google Drive**: Personal account `davidrf@nuclia.com` is set up for Google Drive sync tests.
- **Sharepoint**:
  - Email: `e2e_test_cloud_storage_sync@outlook.com`
  - Password: `xlQfypnaJvm4G6Dy`
  - This account is exclusively used for Sharepoint e2e tests.

> **Note**: In the future, we want to migrate these to official Nuclia service accounts dedicated to testing.

## Seed Files

Each provider test has a `seed_files/` directory alongside it that represents the initial file structure to upload during test setup. The test replicates this tree to the remote storage, so you can visualize and modify the initial state without touching the test code.

```
seed_files/
├── excluded.ignore   # skipped by the file filter (exclude .ignore)
├── document.pdf
├── notes.txt
└── subfolder/
    ├── readme.md
    └── spreadsheet.xlsx
```

All provider tests follow the same pattern — just add/remove/edit files in `seed_files/` to change the initial state.

## Test Lifecycle

Both provider tests (`test_google_drive.py` and `test_sharepoint.py`) validate the full sync lifecycle in five phases:

1. **Initial sync** — uploads seed files + creates a dynamic folder with a dynamic file inside, creates a sync config, triggers sync, and asserts all resources exist in NucliaDB with correct labels. Excluded files (`.ignore`) are verified to be absent.
2. **Incremental create + update** — creates a new file and updates the dynamic file in Drive, triggers sync, and asserts the new resource appears and the updated resource has a newer modification time.
3. **Incremental delete + move out** — deletes/trashes the new file and moves the dynamic folder to the storage root (outside the sync root), triggers sync, and asserts both resources are removed from NucliaDB while remaining seed file resources are intact.
4. **Move back in** — moves the dynamic folder back into the sync root, triggers sync, and asserts the dynamic file resource is re-created with correct labels and `origin.path`.
5. **Rename sync root** — renames the sync root folder, triggers sync, and asserts all remaining resources have their `origin.path` metadata updated to reflect the new folder name.

Cleanup runs in a `finally` block and removes the remote folder, dynamic folder (if orphaned at root), sync config, NucliaDB resources, and labelset.

## Prerequisites

### Google Drive

#### External Connection

Each permanent KB used by the tests must have a pre-existing `GOOGLE_OAUTH` external connection with ID `00000000-0000-7000-8000-000000000000`. This ID is the default value of the `GOOGLE_EXTERNAL_CONNECTION_ID` setting and is used by the test to create sync configs.

#### Refresh Token

The test requires a `GOOGLE_DRIVE_REFRESH_TOKEN` with write permissions (`https://www.googleapis.com/auth/drive` scope).

To generate one using the existing OAuth client:

1. Open the authorization URL in a browser (replace placeholders):

```
https://accounts.google.com/o/oauth2/v2/auth?client_id=CLIENT_ID&redirect_uri=https://aws-me-central-1-1.rag.progress.cloud/api/auth/external_connection/callback&response_type=code&access_type=offline&prompt=consent&scope=https://www.googleapis.com/auth/drive
```

2. Consent with the Google account that owns the test Drive files.

3. After redirect, grab the `code` parameter from the URL.

4. Exchange the code for a refresh token:

```bash
curl -s -X POST https://oauth2.googleapis.com/token \
  -d "code=AUTHORIZATION_CODE" \
  -d "client_id=CLIENT_ID" \
  -d "client_secret=CLIENT_SECRET" \
  -d "redirect_uri=https://aws-me-central-1-1.rag.progress.cloud/api/auth/external_connection/callback" \
  -d "grant_type=authorization_code" | jq .
```

The response contains the `refresh_token`. Set it as `GOOGLE_DRIVE_REFRESH_TOKEN`.

> **Note:** `prompt=consent` forces Google to issue a new refresh token.

### SharePoint / OneDrive

#### External Connection

Each permanent KB used by the tests must have a pre-existing `AZURE_OAUTH` external connection with ID `00000000-0000-7000-8000-000000000001`. This ID is the default value of the `AZURE_EXTERNAL_CONNECTION_ID` setting and is used by the test to create sync configs.

#### Refresh Token

The test requires an `AZURE_REFRESH_TOKEN` with delegated permissions (`Files.ReadWrite.All offline_access` scopes).

To generate one using the existing OAuth client:

1. Open the authorization URL in a browser (replace placeholders):

```
https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id=CLIENT_ID&redirect_uri=http://localhost:8000/api/auth/external_connection/callback&response_type=code&scope=Files.ReadWrite.All+offline_access&prompt=consent
```

2. Consent with the Microsoft account that owns the test OneDrive files.

3. After redirect, grab the `code` parameter from the URL.

4. Exchange the code for a refresh token:

```bash
curl -s -X POST "https://login.microsoftonline.com/common/oauth2/v2.0/token" \
  -d "code=AUTHORIZATION_CODE" \
  -d "client_id=CLIENT_ID" \
  -d "client_secret=CLIENT_SECRET" \
  -d "redirect_uri=http://localhost:8000/api/auth/external_connection/callback" \
  -d "grant_type=authorization_code" \
  -d "scope=Files.ReadWrite.All offline_access"
```

The response contains the `refresh_token`. Set it as `AZURE_REFRESH_TOKEN`.

> **Note:** `prompt=consent` forces a new consent and refresh token.
