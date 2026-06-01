/// <reference types="cypress" />

import { COWORK_ACCOUNT, getCoworkAuthHeader } from '../../support/common';

describe('Content-box MCP', () => {
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

    it('should display "Get the MCP URL" button in step 3', () => {
      cy.get('app-resource-table', { timeout: 5000 }).should('be.visible');
      cy.get('.footer pa-button').contains('Get the MCP URL').should('be.visible');
    });

    it('should open modal with MCP endpoint when clicking button', () => {
      cy.get('.footer pa-button').contains('Get the MCP URL').click();
      cy.get('pa-modal-dialog', { timeout: 5000 }).should('be.visible');
      cy.get('pa-modal-dialog').should('contain', 'MCP');
    });

    it('should allow copying MCP URL from modal', () => {
      cy.get('.footer pa-button').contains('Get the MCP URL').click();
      cy.get('pa-modal-dialog pa-button').contains(/Copy|Copied/).should('be.visible');
      cy.get('pa-modal-dialog').invoke('text').should('include', '/mcp');
    });

    it('should show MCP endpoint URL in modal', () => {
      cy.get('.footer pa-button').contains('Get the MCP URL').click();
      cy.get('pa-modal-dialog pre code').should('be.visible').invoke('text').should('match', /https:\/\/.*\/api\/v1\/kb\/.*\/mcp/);
    });
  });
});
