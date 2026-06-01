/// <reference types="cypress" />

import { COWORK_ACCOUNT, getCoworkAuthHeader } from '../../support/common';

describe('Content-box Chat', () => {
  const zone = COWORK_ACCOUNT.availableZones[0];

  describe(`on ${zone.slug}`, () => {
    let endpoint;
    let authHeader;

    before(() => {
      if (Cypress.env('RUNNING_ENV') !== 'stage') this.skip();
      endpoint = `https://${zone.slug}.${COWORK_ACCOUNT.domain}/api/v1/kb/${zone.permanentKb.id}`;
      authHeader = getCoworkAuthHeader();
    });

    beforeEach(() => {
      cy.loginToCoworkKb(zone);
    });

    it('should render chat widget in step 3', () => {
      cy.get('app-resource-table', { timeout: 5000 }).should('be.visible');
      cy.get('.preview nuclia-chat', { timeout: 5000 }).should('exist');

      cy.get('.preview nuclia-chat').then(($chat) => {
        cy.wrap(null).should(() => {
          expect($chat[0].shadowRoot, 'Shadow root exists').to.not.be.null;
        });
      });

      cy.wait(500);
      cy.get('.preview nuclia-chat').shadow().find('.input-container').should('be.visible');
    });

    it('should produce an answer when typing a question', () => {
      cy.get('.preview nuclia-chat').shadow().find('textarea').type('What is this about?{enter}');
      cy.get('.preview nuclia-chat').shadow().find('.answer', { timeout: 20000 }).should('be.visible');
    });

    it('should show chat container with proper structure', () => {
      cy.get('.preview nuclia-chat').shadow().find('.input-container').should('be.visible');
      cy.get('.preview nuclia-chat').shadow().find('textarea').should('be.visible');
      cy.get('.preview nuclia-chat').shadow().find('button').should('be.visible');
    });

    it('should navigate to history view and back', () => {
      cy.get('app-resource-table', { timeout: 5000 }).should('be.visible');
      cy.get('app-simple-kb .counters .nav').eq(1).find('pa-button').contains('History').click();
      cy.get('app-history-table', { timeout: 5000 }).should('be.visible');
      cy.get('app-simple-kb .counters .nav').eq(0).find('pa-button').contains('Your resources').click();
      cy.get('app-resource-table', { timeout: 5000 }).should('be.visible');
    });
  });
});
