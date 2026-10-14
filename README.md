# e2e testing

![e2e run](https://github.com/nuclia/e2e/actions/workflows/run-e2e.yml/badge.svg)

## Setup

```
yarn install
yarn cypress install
```

## Run manually

Ask a supervisor to give you `cypress.env.json` file and place it on the root folder of your workspace.

- run all the tests from the terminal: `CYPRESS_BASE_URL=https://stashify.cloud yarn cypress run`
- run a specific spec file: `CYPRESS_BASE_URL=https://stashify.cloud yarn cypress run --spec "cypress/e2e/basic/3-widget/find.cy.js"`
- or open cypress dashboard to run them one by one and debug: `CYPRESS_BASE_URL=https://stashify.cloud yarn cypress open`

To run the tests in your local environment:

```shell
CYPRESS_BASE_URL=http://localhost:4200  yarn cypress open
```

## Run with Docker

```
docker build -t e2e .
```

## e2e on prod

When promoting to prod any changes that had impact on the e2e test, the `e2e-on-prod` branch must be rebased on `main`.

The test account email and passwords are saved in the gcp secret manager (project=nuclia-internal, secret=E2E_GITHUB_SECRETS_USER_PWD_PROD)
