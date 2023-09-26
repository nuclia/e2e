import { closeButton, nucliaSearchResultsSelector, viewerSelector } from '../e2e/selectors/widget-selectors';

export const KB_NAME = `new-kb-${Cypress.env('KB_NAME')}`;

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

export function getAuthHeader() {
  return { Authorization: `Bearer ${Cypress.env('BEARER_TOKEN')}` };
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

export const goTo = (menuLabel, popup = false) => {
  cy.get('.app-navbar').trigger('mouseover');
  cy.contains(menuLabel).click();
  if (!popup) {
    // make sure the sidebar collapses
    cy.get('app-user-menu').click();
    cy.get('app-user-menu').click();
  }
};

export const closeViewer = () => {
  cy.get(nucliaSearchResultsSelector)
    .shadow()
    .find(`${viewerSelector} ${closeButton}`)
    .click();
}
