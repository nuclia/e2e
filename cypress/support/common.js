import { closeButton, nucliaSearchResultsSelector, viewerSelector } from '../e2e/selectors/widget-selectors';

export const STANDALONE_KB_NAME = `${Cypress.env('STANDALONE_KB_NAME')}`;
export const STANDALONE_HEADER = {
  'X-NUCLIADB-ROLES': 'MANAGER'
};

export const permanentKb = {
  name: 'permanent',
  id: '096d9070-f7be-40c8-a24c-19c89072e3ff'
}

export const emptyKb = {
  name: 'permanent-empty',
  id: '1efc5a33-bc5a-490c-8b47-b190beee212d'
}

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
  const authHeader = { 'Authorization': `Bearer ${Cypress.env('BEARER_TOKEN')}` };
  cy.request({
    method: 'GET',
    url: `https://stashify.cloud/api/v1/account/testing/kbs`,
    headers: authHeader
  }).then((response) => {
    expect(response.status).to.eq(200);

    if (response.body.length > 2) {
      response.body.forEach(kb => {
        if (!kb.slug.includes('permanent')) {
          cy.request({
            method: 'DELETE',
            url: `https://stashify.cloud/api/v1/account/testing/kb/${kb.slug}`,
            headers: authHeader
          }).then((deleteResponse) => {
            expect(deleteResponse.status).to.eq( 204);
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
export function goToManageAccount () {
  cy.get('app-user-menu').click();
  cy.get('[data-cy="go-to-manage-account"]').click();
}

export const closeViewer = () => {
  cy.get(nucliaSearchResultsSelector)
    .shadow()
    .find(`${viewerSelector} ${closeButton}`)
    .click();
}
