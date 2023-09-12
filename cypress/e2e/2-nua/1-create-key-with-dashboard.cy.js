/// <reference types="cypress" />

import { goTo, user } from '../../support/common';

describe('Create NUA key with the dashboard', () => {
  beforeEach(() => cy.login());

  it('creates and deletes key', () => {
    // TODO: improve resilience by checking through the API first if there is only the permanent e2e NUA key

    goTo('Manage account');
    goTo('Understanding API keys');
    // Create NUA key
    cy.get('.account-nua :not(.client) button')
      .contains('Create new Nuclia understanding API key')
      .click({ force: true });
    cy.get('pa-modal-advanced').should('be.visible');
    cy.get('pa-modal-advanced input[name="title"]').should('be.visible').type('A new key');
    cy.get('pa-modal-advanced').contains('Save').should('be.disabled');
    cy.get('pa-modal-advanced input[name="email"]').type(user.email);
    cy.get('pa-modal-advanced').contains('Save').should('be.enabled');
    cy.get('pa-modal-advanced').contains('Save').click();
    cy.get('pa-modal-dialog').contains('Copy').click();
    cy.get('pa-modal-dialog').contains('Close').click();

    // Delete NUA key
    cy.get('.account-nua .client-row').contains('A new key');
    cy.get(`[data-cy="A new key-delete"]`).click();
    cy.get('[qa="confirmation-dialog-confirm-button"]').click();
  });
});
