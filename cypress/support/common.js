import { closeButton, nucliaSearchResultsSelector, viewerSelector } from '../e2e/selectors/widget-selectors';

export const ZONES = {
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
    nuaKey: `${Cypress.env('NUA_KEY')}`
  }],
};
export const ACCOUNT_PROD = {
  id: '5cec111b-ea23-4b0c-a82a-d1a666dd1fd2',
  slug: 'nuclia-testing',
  domain: 'nuclia.cloud',
  availableZones: [{
    slug: ZONES['europe'],
    nuaKey: `${Cypress.env('NUA_KEY_PROD_EUROPE')}`
  }, {
    slug: ZONES['usa'],
    nuaKey: `${Cypress.env('NUA_KEY_PROD_USA')}`
  }],
};

export const ACCOUNT = Cypress.env('CYPRESS_RUNNING_ENV') === 'prod' ? ACCOUNT_PROD : ACCOUNT_STAGE;

export const permanentKb = {
  name: 'permanent',
  slug: 'permanent',
  id: Cypress.env('CYPRESS_RUNNING_ENV') === 'prod' ? 'f639477f-dd3d-4509-b278-7ab20ff73bd1' : '096d9070-f7be-40c8-a24c-19c89072e3ff',
  zone: ZONES['europe'],
};
export const emptyKb = {
  name: 'permanent-empty',
  slug: 'permanent-empty',
  id: Cypress.env('CYPRESS_RUNNING_ENV') === 'prod' ? '6176242a-b15d-459b-b4b9-5740fc1fed72' : '1efc5a33-bc5a-490c-8b47-b190beee212d',
  zone: ZONES['europe'],
};

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

/**
 * Keep only permanent KB on specified zone and account.
 * @param zone europe | usa
 */
export function onlyPermanentKb(zone = 'europe') {
  const authHeader = { Authorization: `Bearer ${Cypress.env('BEARER_TOKEN')}` };
  cy.request({
    method: 'GET',
    url: `https://${ZONES[zone]}.${ACCOUNT.domain}/api/v1/account/${ACCOUNT.id}/kbs`,
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
