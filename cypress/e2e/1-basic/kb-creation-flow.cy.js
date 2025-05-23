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
      // Zones are loaded asynchronously, and we noticed some flakiness on prod because cypress selected the zone before angular was totally ready
      // So we check the controls visibility first to make sure cycle detection will work when cypress clicks on the zone
      cy.get('[formcontrolname="title"] input', { timeout: 10000 }).type(newKbName);
      cy.get('[formcontrolname="description"] textarea').type('Some kb');
      cy.get('[formcontrolname="zone"] pa-radio', { timeout: 10000 }).should('be.visible');
      cy.get('[formcontrolname="zone"] pa-radio').contains(zone.title).click();
      cy.get('[data-cy="new-kb-save-button"] button').should('be.enabled').click();
      cy.get(`[data-cy="${newKbName}-link"]`, { timeout: 20000 }).should('contain', newKbName);
      cy.get(`[data-cy="${newKbName}-link"]`).click();
      cy.location('pathname').should('equal', `/at/${ACCOUNT.slug}/${zone.slug}/${newKbName}`);
      cy.get('app-kb-switch').should('contain', newKbName);

      // Deletion test
      goToManageAccount();
      goTo('go-to-account-kbs');
      cy.get(`[data-cy="${newKbName}-link"]`).contains(newKbName);
      cy.get(`[data-cy="${newKbName}-delete"]`).click();
      cy.get('[qa="confirmation-dialog-confirm-button"]').click();
      cy.get('.account-kbs-list .account-kb', { timeout: 10000 }).should('have.length', ACCOUNT.permanentKbCount);
    });
  });
});
