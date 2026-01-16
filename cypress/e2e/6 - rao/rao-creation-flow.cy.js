/// <reference types="cypress" />

import { ACCOUNT, goTo, goToManageAccount, onlyPermanentKb } from '../../support/common';

describe('RAO creation flow', () => {
  ACCOUNT.availableZones.forEach((zone) => {
    beforeEach(() => {
      onlyPermanentKb('agent_no_memory');
    });

    it(`should allow to create a new RAO workflow and then delete it on ${zone.slug}`, () => {
      const newAragName = `new-rao-${Date.now()}`;
      cy.login(zone);

      // creation test
      goToManageAccount();
      goTo('go-to-retrieval-agents');
      cy.get('[data-cy="add-arag"]').click();
      // Zones are loaded asynchronously, and we noticed some flakiness on prod because cypress selected the zone before angular was totally ready
      // So we check the controls visibility first to make sure cycle detection will work when cypress clicks on the zone
      cy.get('[formcontrolname="name"] input', { timeout: 10000 }).type(newAragName);
      cy.get('[formcontrolname="zone"] pa-radio', { timeout: 10000 }).should('be.visible');
      cy.get('[formcontrolname="zone"] pa-radio').contains(zone.title).click();
      cy.get('[data-cy="new-arag-save-button"] button').should('be.enabled').click();
      cy.get(`[data-cy="${newAragName}-link"]`, { timeout: 20000 }).should('contain', newAragName);
      cy.get(`[data-cy="${newAragName}-link"]`).click();
      cy.location('pathname').should('equal', `/at/${ACCOUNT.slug}/${zone.slug}/arag/${newAragName}`);
      cy.get('app-kb-switch').should('contain', newAragName);

      // workflow config
      cy.get('.agent-dashboard-toolbar [aria-label="Add node"]').click();
      // TODO: fix the right panel open/collapse behavior, it is broken under Cypress

      // Deletion test
      goToManageAccount();
      goTo('go-to-retrieval-agents');
      cy.get(`[data-cy="${newAragName}-link"]`).contains(newAragName);
      cy.get(`.account-arag-content pa-button`).click();
      cy.get(`.account-arag-content pa-option[icon="trash"]`).click();
      cy.get('[qa="confirmation-dialog-confirm-button"]').click();
      cy.get('.account-arag-content nsi-info-card', { timeout: 10000 }).should('be.visible');
    });
  });
});
