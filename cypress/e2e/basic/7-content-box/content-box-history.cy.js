/// <reference types="cypress" />

import { COWORK_ACCOUNT } from '../../../support/common';

describe('Content-box History', () => {
  const zone = COWORK_ACCOUNT.availableZones[0];

  describe(`on ${zone.slug}`, () => {
    beforeEach(() => {
      cy.loginToCoworkKb(zone);
    });

    it('should display resources and history buttons in step 3', () => {
      cy.get('.footer pa-button').contains('Your resources').should('be.visible');
      cy.get('.footer pa-button').contains('History').should('be.visible');
    });

    it('should display "Upload files" button in step 3', () => {
      cy.get('.footer pa-button').contains('Upload').should('be.visible');
    });
  });
});
