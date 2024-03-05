import { closeButton, nucliaSearchResultsSelector, viewerSelector } from '../e2e/selectors/widget-selectors';

const ZONES = {
  europe: 'europe-1',
  usa: 'aws-us-east-2-1'
}

export const STANDALONE_KB_NAME = `${Cypress.env('STANDALONE_KB_NAME')}`;
export const STANDALONE_HEADER = {
  'X-NUCLIADB-ROLES': 'MANAGER',
};

export const ACCOUNT_STAGE = {
  id: '23d9209a-34be-4648-8ef0-5b522f9976be',
  slug: 'testing',
  domain: 'stashify.cloud',
  availableZones: [{
    slug: ZONES['europe'],
    nuaKey: `${Cypress.env('NUA_KEY')}`,
    permanentKb: {
      name: 'permanent',
      slug: 'permanent',
      id: '096d9070-f7be-40c8-a24c-19c89072e3ff',
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
  }],
};

export const ACCOUNT_PROD = {
  id: '5cec111b-ea23-4b0c-a82a-d1a666dd1fd2',
  slug: 'nuclia-testing',
  domain: 'nuclia.cloud',
  availableZones: [{
    slug: ZONES['europe'],
    nuaKey: `${Cypress.env('NUA_KEY_PROD_EUROPE')}`,
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
    findUrl: 'https://nuclia.github.io/frontend/e2e/prod/find-europe.html'
  }, {
    slug: ZONES['usa'],
    nuaKey: `${Cypress.env('NUA_KEY_PROD_USA')}`,
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
    findUrl: 'https://nuclia.github.io/frontend/e2e/prod/find-usa.html'
  }],
};

export const ACCOUNT = `${Cypress.env('RUNNING_ENV')}` === 'prod' ? ACCOUNT_PROD : ACCOUNT_STAGE;

export const user = {
  email: `${Cypress.env('USER_NAME')}`,
  password: `${Cypress.env('USER_PWD')}`,
};

export function getAuthHeader(synchronous = true) {
  const headers = { Authorization: `Bearer ${Cypress.env('BEARER_TOKEN')}` };
  if (synchronous) {
    headers['x-synchronous'] = true;
  }
  return headers;
}

export function onlyPermanentKb() {
  const authHeader = { Authorization: `Bearer ${Cypress.env('BEARER_TOKEN')}` };
  ACCOUNT.availableZones.forEach((zone) => {
    cy.request({
      method: 'GET',
      url: `https://${zone.slug}.${ACCOUNT.domain}/api/v1/account/${ACCOUNT.id}/kbs`,
      headers: authHeader,
    }).then((response) => {
      expect(response.status).to.eq(200);

      if (response.body.length > 2) {
        response.body.forEach((kb) => {
          if (!kb.slug.includes('permanent')) {
            cy.request({
              method: 'DELETE',
              url: `https://${ACCOUNT.domain}/api/v1/account/${ACCOUNT.slug}/kb/${kb.slug}`,
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
