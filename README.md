# e2e testing

![e2e run](https://github.com/nuclia/e2e/actions/workflows/run-e2e.yml/badge.svg)

## Setup

```
yarn install
```

## Run manually

- run all the tests from the terminal: ```cypress run```
- run a specific spec file: ```cypress run --spec "cypress/e2e/3-widget/1-search.cy.js"```
- or open cypress dashboard to run them one by one and debug: ```yarn run cypress open```

By default, tests are running on stage (thanks to `baseUrl` set in `cypress.config.js`). 
To run the tests in your local environment:
```shell
CYPRESS_BASE_URL=http://localhost:4200  cypress run
```

## Run with Docker

```
docker build -t e2e .
```
