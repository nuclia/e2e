/// <reference types="cypress" />

import { ACCOUNT, getAuthHeader, goTo, goToManageAccount, user } from '../../support/common';

describe('Create NUA key with the dashboard', () => {
  before(() => {
    const authHeader = getAuthHeader();
    // https://stashify.cloud/api/v1/account/testing/nua_clients
    cy.request({
      method: 'GET',
      url: `https://europe-1.stashify.cloud/api/v1/account/${ACCOUNT.id}/nua_clients`,
      headers: authHeader
    }).then(response => {
      expect(response.status).to.eq(200);
      const clients = response.body['clients'] || [];
      if (clients.length > 1) {
        clients.filter((client) => client['title'] !== 'e2e').forEach(client => {
          cy.request({
            method: 'DELETE',
            url: `https://europe-1.stashify.cloud/api/v1/account/${ACCOUNT.id}/nua_client/${client.client_id}`,
            headers: authHeader
          }).then(patchResponse => expect(patchResponse.status).to.eq(204));
        });
      }
    });
  });

  beforeEach(() => cy.login());

  it('creates and deletes key', () => {
    goToManageAccount();
    goTo('go-to-nua-keys');
    // Create NUA key
    cy.get('[data-cy="open-create-nua-key-dialog"]').click();
    cy.get('pa-modal-advanced').should('be.visible');
    cy.get('pa-modal-advanced input[name="title"]').should('be.visible').type('A new key');
    cy.get('pa-modal-advanced').get('[data-cy="save-nua-client"]').click();
    cy.get('pa-modal-dialog').get('[data-cy="copy-token"]').click();
    cy.get('pa-modal-dialog').get('[data-cy="close-token-dialog"]').click();

    // Delete NUA key
    cy.get('.page-spacing .client-row').contains('A new key');
    cy.get(`[data-cy="A new key-delete"]`).click();
    cy.get('[qa="confirmation-dialog-confirm-button"]').click();
  });
});
