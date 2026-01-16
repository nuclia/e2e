import { closeButton, nucliaSearchResultsSelector, viewerSelector } from '../e2e/selectors/widget-selectors';

const ZONES = {
  europe: 'europe-1',
  usa: 'aws-us-east-2-1',
  dev: 'gcp-dev-1',
};

export const STANDALONE_KB_NAME = `${Cypress.env('STANDALONE_KB_NAME')}`;
export const STANDALONE_HEADER = {
  'X-NUCLIADB-ROLES': 'MANAGER',
};

export const ACCOUNT_STAGE = {
  id: '23d9209a-34be-4648-8ef0-5b522f9976be',
  slug: 'testing',
  domain: 'stashify.cloud',
  hasMultipleZones: true,
  availableZones: [
    {
      slug: ZONES['europe'],
      title: 'Europe',
      permanentKb: {
        name: 'permanent',
        slug: 'permanent',
        id: 'baa24d32-9240-4d90-bd00-2e6f25b13668',
        zone: ZONES['europe'],
      },
      emptyKb: {
        name: 'permanent-empty',
        slug: 'permanent-empty',
        id: '1efc5a33-bc5a-490c-8b47-b190beee212d',
        zone: ZONES['europe'],
      },
      askUrl: 'https://nuclia.github.io/frontend/e2e/ask.html',
      citationsUrl: 'https://nuclia.github.io/frontend/e2e/citations.html',
      findUrl: 'https://nuclia.github.io/frontend/e2e/find.html',
      searchUrl: 'https://nuclia.github.io/frontend/e2e/search.html',
    },
  ],
  permanentKbCount: 2,
};

export const ACCOUNT_PROD = {
  id: '5cec111b-ea23-4b0c-a82a-d1a666dd1fd2',
  slug: 'nuclia-testing',
  domain: 'nuclia.cloud',
  hasMultipleZones: true,
  availableZones: [
    {
      slug: ZONES['europe'],
      title: 'Europe',
      permanentKb: {
        name: 'permanent',
        slug: 'permanent',
        id: 'f639477f-dd3d-4509-b278-7ab20ff73bd1',
        zone: ZONES['europe'],
      },
      emptyKb: {
        name: 'permanent-empty',
        slug: 'permanent-empty',
        id: '6176242a-b15d-459b-b4b9-5740fc1fed72',
        zone: ZONES['europe'],
      },
      askUrl: 'https://nuclia.github.io/frontend/e2e/prod/ask-europe.html',
      citationsUrl: 'https://nuclia.github.io/frontend/e2e/prod/citations-europe.html',
      findUrl: 'https://nuclia.github.io/frontend/e2e/prod/find-europe.html',
      searchUrl: 'https://nuclia.github.io/frontend/e2e/prod/search-europe.html',
    },
    {
      slug: ZONES['usa'],
      title: 'USA',
      permanentKb: {
        name: 'permanent USA',
        slug: 'permanent-usa',
        id: 'b6805475-88da-47a0-a8fb-a044919f692e',
        zone: ZONES['usa'],
      },
      emptyKb: {
        name: 'permanent-empty USA',
        slug: 'permanent-empty-usa',
        id: '53861c47-20b2-4c6f-bd7a-3286ca5bec13',
        zone: ZONES['usa'],
      },
      askUrl: 'https://nuclia.github.io/frontend/e2e/prod/ask-usa.html',
      citationsUrl: 'https://nuclia.github.io/frontend/e2e/prod/citations-usa.html',
      findUrl: 'https://nuclia.github.io/frontend/e2e/prod/find-usa.html',
      searchUrl: 'https://nuclia.github.io/frontend/e2e/prod/search-usa.html',
    },
  ],
  permanentKbCount: 4,
};

export const ACCOUNT_DEV = {
  //eric+e2e@nuclia.com
  id: '22e77dea-3552-45ad-b387-1c8755f9c3cc',
  slug: 'testing',
  domain: 'gcp-global-dev-1.nuclia.io',
  hasMultipleZones: false,
  availableZones: [
    {
      slug: ZONES['dev'],
      title: 'Regional gcp-dev-1',
      permanentKb: {
        name: 'permanent',
        slug: 'permanent',
        id: '0d773aed-bfb8-4228-a9d7-ed9f0ff171eb',
        zone: ZONES['dev'],
      },
      emptyKb: {
        name: 'permanent-empty',
        slug: 'permanent-empty',
        id: '065ce433-e294-494c-9dc7-56c7230dbf16',
        zone: ZONES['dev'],
      },
      askUrl: 'https://nuclia.github.io/frontend/e2e/dev/ask.html',
      citationsUrl: 'https://nuclia.github.io/frontend/e2e/dev/citations.html',
      findUrl: 'https://nuclia.github.io/frontend/e2e/dev/find.html',
      searchUrl: 'https://nuclia.github.io/frontend/e2e/dev/search.html',
    },
  ],
  permanentKbCount: 2,
};

export const ACCOUNT =
  `${Cypress.env('RUNNING_ENV')}` === 'prod'
    ? ACCOUNT_PROD
    : `${Cypress.env('RUNNING_ENV')}` === 'dev'
    ? ACCOUNT_DEV
    : ACCOUNT_STAGE;

export const user = {
  email: `${Cypress.env('USER_NAME')}`,
  password: `${Cypress.env('USER_PWD')}`,
};

export const UI_STARTER = !!Cypress.env('UI_STARTER');

export function getAuthHeader(synchronous = true) {
  const headers = { Authorization: `Bearer ${Cypress.env('BEARER_TOKEN')}` };
  if (synchronous) {
    headers['x-synchronous'] = true;
  }
  return headers;
}

export function onlyPermanentKb(mode) {
  const authHeader = { Authorization: `Bearer ${Cypress.env('BEARER_TOKEN')}` };
  ACCOUNT.availableZones.forEach((zone) => {
    cy.request({
      method: 'GET',
      url: `https://${zone.slug}.${ACCOUNT.domain}/api/v1/account/${ACCOUNT.id}/kbs${mode ? '?mode=' + mode : ''}`,
      headers: authHeader,
    }).then((response) => {
      expect(response.status).to.eq(200);

      if (response.body.length > 2) {
        response.body.forEach((kb) => {
          if (!kb.slug.includes('permanent')) {
            cy.request({
              method: 'DELETE',
              url: `https://${zone.slug}.${ACCOUNT.domain}/api/v1/account/${ACCOUNT.id}/kb/${kb.id}`,
              headers: authHeader,
            }).then((deleteResponse) => {
              expect(deleteResponse.status).to.eq(204);
            });
          }
        });
      }
    });
  });
}

export const goTo = (navbarItemSelector, popup = false) => {
  cy.get('.app-navbar').trigger('mouseover');
  cy.get(`[data-cy="${navbarItemSelector}"]`).click();
  if (!popup) {
    // make sure the sidebar collapses
    cy.get('app-kb-switch').click();
    cy.get('app-kb-switch').click();
  }
};

export function goToManageAccount() {
  cy.get('app-user-menu').click();
  cy.get('[data-cy="go-to-manage-account"]').click();
}

export const closeViewer = () => {
  cy.get(nucliaSearchResultsSelector).shadow().find(`${viewerSelector} ${closeButton}`).click();
};
