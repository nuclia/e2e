/// <reference types="cypress" />

import { ACCOUNT, goTo, goToManageAccount, onlyPermanentKb } from '../../support/common';

describe('KB creation flow', () => {
  ACCOUNT.availableZones.forEach((zone) => {
    beforeEach(() => {
      onlyPermanentKb();
    });

    it(`should allow to create a new kb and then delete it on ${zone.slug}`, () => {
      const newKbName = `new-kb-${Date.now()}`;
      cy.login(zone);

      // creation test
      goToManageAccount();
      goTo('go-to-account-kbs');
      cy.get('[data-cy="add-kb"]').click();
      cy.get('[formcontrolname="title"] input').type(newKbName);
      cy.get('[formcontrolname="description"] textarea').type('Some kb');
      cy.get('[data-cy="new-kb-zone-select"]').click();
      cy.get('pa-option').contains(zone.title).click();
      cy.get('[data-cy="new-kb-save-button"] button').should('be.enabled').click();
      cy.get(`[data-cy="${newKbName}-link"]`, { timeout: 10000 }).should('contain', newKbName);
      cy.get(`[data-cy="${newKbName}-link"]`).click();
      cy.location('pathname').should('equal', `/at/${ACCOUNT.slug}/${zone.slug}/${newKbName}`);
      cy.get('app-kb-switch').should('contain', newKbName);

      // Deletion test
      goToManageAccount();
      goTo('go-to-account-kbs');
      cy.get(`[data-cy="${newKbName}-link"]`).contains(newKbName);
      cy.get(`[data-cy="${newKbName}-delete"]`).click();
      cy.get('[qa="confirmation-dialog-confirm-button"]').click();
      cy.get('.account-kbs-list .account-kb').should('have.length', 2);
    });
  });

});
