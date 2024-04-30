/// <reference types="cypress" />

import { ACCOUNT, getAuthHeader, goTo } from '../../support/common';

describe('Change KB settings', () => {
  const authHeader = getAuthHeader();

  ACCOUNT.availableZones.forEach((zone) => {
    const endpoint = `https://${zone.slug}.${ACCOUNT.domain}/api/v1/account/${ACCOUNT.id}/kb/${zone.emptyKb.id}`;

    before(() => {
      cy.request({
        method: 'PATCH',
        url: `${endpoint}`,
        headers: authHeader,
        body: {
          description: `DO NOT DELETE\nKnowledge box used to test content addition through E2E tests, and should always be empty at the end of the tests`,
        },
      }).then((response) => {
        expect(response.status).to.eq(200);
      });
    });

    it(`should allow to change the kb settings on ${zone.slug}`, () => {
      cy.loginToEmptyKb(zone);
      goTo('go-to-advanced');
      goTo('go-to-settings');
      cy.get('main').scrollTo('bottom');
      cy.get('[data-cy="save-kb-settings"]').get('button').should('be.disabled');
      cy.get('main').scrollTo('top');
      cy.get(`[formcontrolname="description"] textarea`).type(
        '\nWhy did you say that? Now I feel like I want to delete this kb.\n'
      );
      cy.get('main').scrollTo('bottom');
      cy.get('[data-cy="save-kb-settings"]').click();
      cy.get('.pa-toast-wrapper').should('contain', 'The new settings have been saved successfully');
    });
  });
});
