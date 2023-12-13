/// <reference types="cypress" />

import { emptyKb, getAuthHeader, goTo } from '../../support/common';

describe('Change KB settings', () => {
  const endpoint = `https://stashify.cloud/api/v1/account/testing/kb/${emptyKb.name}`;
  const authHeader = getAuthHeader();

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

  it('should allow to change the kb settings', () => {
    cy.loginToEmptyKb();
    goTo('go-to-advanced');
    goTo('go-to-settings');
    cy.get('.dashboard-content').scrollTo('bottom');
    cy.get('[data-cy="save-kb-settings"]').get('button').should('be.disabled');
    cy.get('.dashboard-content').scrollTo('top');
    cy.get(`[formcontrolname="description"] textarea`).type(
      '\nWhy did you say that? Now I feel like I want to delete this kb.\n'
    );
    cy.get('.dashboard-content').scrollTo('bottom');
    cy.get('[data-cy="save-kb-settings"]').click();
    cy.get('.pa-toast-wrapper').should('contain', 'The new settings have been saved successfully');
  });
});
