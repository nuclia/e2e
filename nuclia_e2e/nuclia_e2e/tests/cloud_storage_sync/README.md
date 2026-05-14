# Cloud Storage Sync E2E Tests

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

The Google Drive test (`test_google_drive.py`) validates the full sync lifecycle in three phases:

1. **Initial sync** — uploads seed files + a dynamic file to a temporary Drive folder, creates a sync config, triggers sync, and asserts all resources exist in NucliaDB with correct labels. Excluded files (`.ignore`) are verified to be absent.
2. **Incremental create + update** — creates a new file and updates the dynamic file in Drive, triggers sync, and asserts the new resource appears and the updated resource has a newer modification time.
3. **Incremental delete** — trashes the new file in Drive, triggers sync, and asserts it is removed from NucliaDB while remaining resources are intact.

Cleanup runs in a `finally` block and removes the Drive folder, sync config, NucliaDB resources, and labelset.

## Prerequisites

### External Connection

Each permanent KB used by the tests must have a pre-existing `GOOGLE_OAUTH` external connection with ID `00000000-0000-7000-8000-000000000000`. This ID is the default value of the `EXTERNAL_CONNECTION_ID` setting and is used by the test to create sync configs.

### Google Drive Refresh Token

The test requires a `GOOGLE_DRIVE_REFRESH_TOKEN` with write permissions (`https://www.googleapis.com/auth/drive` scope).

To generate one using the existing OAuth client:

1. Open the authorization URL in a browser (replace placeholders):

```
https://accounts.google.com/o/oauth2/v2/auth?client_id=CLIENT_ID&redirect_uri=http://localhost:8000/api/auth/external_connection/callback&response_type=code&access_type=offline&prompt=consent&scope=https://www.googleapis.com/auth/drive
```

2. Consent with the Google account that owns the test Drive files.

3. After redirect, grab the `code` parameter from the URL.

4. Exchange the code for a refresh token:

```bash
curl -s -X POST https://oauth2.googleapis.com/token \
  -d "code=AUTHORIZATION_CODE" \
  -d "client_id=CLIENT_ID" \
  -d "client_secret=CLIENT_SECRET" \
  -d "redirect_uri=http://localhost:8000/api/auth/external_connection/callback" \
  -d "grant_type=authorization_code" | jq .
```

The response contains the `refresh_token`. Set it as `GOOGLE_DRIVE_REFRESH_TOKEN`.

> **Note:** `prompt=consent` forces Google to issue a new refresh token. The authorization code expires within minutes and is single-use — exchange it immediately.
