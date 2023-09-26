/// <reference types="cypress" />

import { emptyKb, getAuthHeader, goTo } from '../../support/common';

describe('Manage content', () => {
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
    goTo('Settings');
    cy.scrollTo('bottom');
    cy.contains('Save').should('be.disabled');
    cy.scrollTo('top');
    cy.get(`[formcontrolname="description"] textarea`).type(
      '\nWhy did you say that? Now I feel like I want to delete this kb.\n'
    );
    cy.scrollTo('bottom');
    cy.contains('Save').should('be.enabled');
    cy.contains('Save').click();
    cy.get('.pa-toast-wrapper').should('contain', 'The new settings have been saved successfully');
  });
});
