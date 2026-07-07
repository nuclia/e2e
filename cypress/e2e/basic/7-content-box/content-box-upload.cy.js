/// <reference types="cypress" />

import { COWORK_ACCOUNT, getCoworkAuthHeader } from '../../../support/common';

describe('Content-box Upload', () => {
  const zone = COWORK_ACCOUNT.availableZones[0];

  describe(`on ${zone.slug}`, () => {
    before(() => {
      const endpoint = `https://${zone.slug}.${COWORK_ACCOUNT.domain}/api/v1/kb/${zone.emptyKb.id}`;
      const authHeader = getCoworkAuthHeader();

      cy.task('log', 'Cleaning up all resources from empty KB before upload tests');
      cy.request({
        method: 'GET',
        url: `${endpoint}/resources`,
        headers: authHeader,
      }).then((response) => {
        const resources = response.body.resources || [];
        cy.task('log', `Found ${resources.length} resources to clean up`);
        resources.forEach((resource) => {
          cy.request({
            method: 'DELETE',
            url: `${endpoint}/resource/${resource.id}`,
            headers: authHeader,
            failOnStatusCode: false,
          });
        });
        if (resources.length > 0) {
          cy.wait(2000);
        }
      });
    });

    beforeEach(() => {
      cy.loginToCoworkEmptyKb(zone);
    });

    it('should upload a file when selected', () => {
      cy.get('input[type="file"]').attachFile('hello.txt');
      cy.wait(2000);
      cy.get('app-resource-table pa-table-row').should('have.length.at.least', 1);
      cy.get('app-resource-table').should('contain', 'hello');
    });

    it('should open delete confirmation modal when clicking delete button', () => {
      cy.get('input[type="file"]').attachFile('hello2.txt');
      cy.wait(2000);
      cy.get('app-resource-table', { timeout: 5000 }).should('be.visible');
      cy.get('app-resource-table pa-button[icon="trash"]').first().click();
      cy.get('pa-confirmation-dialog').should('be.visible');
      cy.get('pa-confirmation-dialog').should('contain', 'Delete');
      cy.get('pa-confirmation-dialog [qa="confirmation-dialog-cancel-button"]').click();
    });

    it('should remove resource from table after confirming delete', () => {
      cy.get('input[type="file"]').attachFile('hello3.txt');
      cy.wait(2000);
      cy.get('app-resource-table', { timeout: 5000 }).should('be.visible');
      cy.get('app-resource-table pa-table-row').then(($rows) => {
        const initialCount = $rows.length;
        cy.get('app-resource-table pa-button[icon="trash"]').first().click();
        cy.get('pa-confirmation-dialog [qa="confirmation-dialog-confirm-button"]').click();
        cy.wait(2000);
        cy.get('app-resource-table pa-table-row').should('have.length', initialCount - 1);
      });
    });
  });
});
