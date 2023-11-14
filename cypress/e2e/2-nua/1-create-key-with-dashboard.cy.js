/// <reference types="cypress" />

import { goTo, user } from '../../support/common';

describe('Create NUA key with the dashboard', () => {
  beforeEach(() => cy.login());

  it('creates and deletes key', () => {
    // TODO: improve resilience by checking through the API first if there is only the permanent e2e NUA key

    goTo('go-to-manage-account');
    goTo('go-to-nua-keys');
    // Create NUA key
    cy.get('[data-cy="open-create-nua-key-dialog"]').click();
    cy.get('pa-modal-advanced').should('be.visible');
    cy.get('pa-modal-advanced input[name="title"]').should('be.visible').type('A new key');
    cy.get('pa-modal-advanced').get('[data-cy="save-nua-client"]').get('button').should('be.disabled');
    cy.get('pa-modal-advanced input[name="contact"]').type(user.email);
    cy.get('pa-modal-advanced').get('[data-cy="save-nua-client"]').click();
    cy.get('pa-modal-dialog').get('[data-cy="copy-token"]').click();
    cy.get('pa-modal-dialog').get('[data-cy="close-token-dialog"]').click();

    // Delete NUA key
    cy.get('.account-nua .client-row').contains('A new key');
    cy.get(`[data-cy="A new key-delete"]`).click();
    cy.get('[qa="confirmation-dialog-confirm-button"]').click();
  });
});
