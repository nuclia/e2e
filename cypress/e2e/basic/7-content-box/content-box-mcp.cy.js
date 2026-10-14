/// <reference types="cypress" />

import { COWORK_ACCOUNT } from '../../../support/common';

describe('Content-box MCP', () => {
  const zone = COWORK_ACCOUNT.availableZones[0];

  describe(`on ${zone.slug}`, () => {
    beforeEach(() => {
      cy.loginToCoworkKb(zone);
    });

    function openMcpModal() {
      cy.get('.footer pa-button[icon="more-vertical"]').click();
      cy.get('pa-option').contains('Get the MCP URL').click();
    }

    it('should display "Get the MCP URL" button in step 3', () => {
      cy.get('.footer pa-button[icon="more-vertical"]').click();
      cy.get('pa-option').contains('Get the MCP URL').should('be.visible');
    });

    it('should open modal with MCP endpoint when clicking button', () => {
      openMcpModal();
      cy.get('pa-modal-dialog', { timeout: 5000 }).should('be.visible');
      cy.get('pa-modal-dialog').should('contain', 'MCP');
    });

    it('should allow copying MCP URL from modal', () => {
      openMcpModal();
      cy.get('pa-modal-dialog pa-button').contains(/Copy|Copied/).should('be.visible');
      cy.get('pa-modal-dialog').invoke('text').should('include', '/mcp');
    });

    it('should show MCP endpoint URL in modal', () => {
      openMcpModal();
      cy.get('pa-modal-dialog pre code').should('be.visible').invoke('text').should('match', /https:\/\/.*\/api\/v1\/kb\/.*\/mcp/);
    });
  });
});
