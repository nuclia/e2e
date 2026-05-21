/// <reference types="cypress" />

import { ACCOUNT, getAuthHeader, goTo, goToManageAccount } from '../../support/common';

describe('Create NUA key with the dashboard', () => {
  const authHeader = getAuthHeader();
  ACCOUNT.availableZones.forEach((zone) => {
    beforeEach(() => {
      // Clean stale NUA clients across ALL zones (getNUAClients aggregates from all zones)
      cy.request({
        method: 'GET',
        url: `https://${ACCOUNT.domain}/api/v1/zones`,
        headers: authHeader,
      }).then((zonesResponse) => {
        const apiZones = zonesResponse.body || [];
        apiZones.forEach((apiZone) => {
          cy.request({
            method: 'GET',
            url: `https://${apiZone.slug}.${ACCOUNT.domain}/api/v1/account/${ACCOUNT.id}/nua_clients`,
            headers: authHeader,
            failOnStatusCode: false,
          }).then((response) => {
            if (response.status === 200) {
              const clients = response.body['clients'] || [];
              clients
                .filter((client) => !client['title'].includes('e2e'))
                .forEach((client) => {
                  cy.request({
                    method: 'DELETE',
                    url: `https://${apiZone.slug}.${ACCOUNT.domain}/api/v1/account/${ACCOUNT.id}/nua_client/${client.client_id}`,
                    headers: authHeader,
                  });
                });
            }
          });
        });
      });

      cy.login(zone);
    });

    describe(`on ${zone.slug}`, () => {
      it('creates and deletes key', () => {
        goToManageAccount();
        goTo('go-to-nua-keys');
        // Create NUA key
        cy.get('[data-cy="open-create-nua-key-dialog"]').click();
        cy.get('pa-modal-advanced').should('be.visible');
        cy.get('pa-modal-advanced input[name="title"]').should('be.visible').type('A new key');
        if (ACCOUNT.hasMultipleZones) {
          cy.get('[formcontrolname="zone"] .pa-field-container').should('not.have.class', 'pa-readonly');
          cy.get('[formcontrolname="zone"]').click();
          cy.get('[formcontrolname="zone"] pa-option').contains(zone.title).click();
        }
        cy.get('pa-modal-advanced').get('[data-cy="save-nua-client"]').click();
        cy.get('pa-modal-dialog').get('[data-cy="close-token-dialog"]').click();

        // Delete NUA key
        cy.get('.page-spacing .client-row').contains('A new key');
        cy.get(`[data-cy="A new key-delete"]`).click();
        cy.get('[qa="confirmation-dialog-confirm-button"]').click();
      });
    });
  });
});
