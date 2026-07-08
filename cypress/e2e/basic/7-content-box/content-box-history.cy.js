/// <reference types="cypress" />

import { COWORK_ACCOUNT } from '../../../support/common';

describe('Content-box History', () => {
  const zone = COWORK_ACCOUNT.availableZones[0];

  describe(`on ${zone.slug}`, () => {
    beforeEach(() => {
      cy.loginToCoworkKb(zone);
    });

    it('should display history tab in step 3', () => {
      cy.get('app-resource-table', { timeout: 5000 }).should('be.visible');
      cy.get('app-simple-kb .counters button.nav').should('have.length', 2);
      cy.get('app-simple-kb .counters button.nav').should('contain.text', 'History');
    });

    it('should display "Upload files" button in step 3', () => {
      cy.get('app-resource-table', { timeout: 5000 }).should('be.visible');
      cy.get('.footer pa-button').contains('Upload').should('be.visible');
    });
  });
});
