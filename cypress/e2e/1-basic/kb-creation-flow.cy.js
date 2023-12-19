/// <reference types="cypress" />

import { goTo, goToManageAccount, onlyPermanentKb } from '../../support/common';

describe('KB creation flow', () => {
  before(() => {
    onlyPermanentKb();
  });

  it('should allow to create a new kb and then delete it', () => {
    const newKbName = `new-kb-${Date.now()}`;
    cy.login();

    // creation test
    goToManageAccount();
    goTo('go-to-account-kbs');
    cy.get('[data-cy="add-kb"]').click();
    cy.get('app-kb-add [formcontrolname="title"] input').type(newKbName);
    cy.get('app-kb-add [formcontrolname="description"] textarea').type('Some kb');
    cy.get('app-kb-add').contains('Next').click();
    cy.get('app-kb-add').contains('Save').click();
    cy.get(`[data-cy="${newKbName}-link"]`, { timeout: 10000 }).should('contain', newKbName);
    cy.get(`[data-cy="${newKbName}-link"]`).click();
    cy.location('pathname').should('equal', `/at/testing/europe-1/${newKbName}`);
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
