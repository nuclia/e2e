/// <reference types="cypress" />

import { COWORK_ACCOUNT, getCoworkAuthHeader } from '../../support/common';

describe('Content-box Resources', () => {
  const zone = COWORK_ACCOUNT.availableZones[0];

  describe(`on ${zone.slug}`, () => {
    let endpoint;
    let authHeader;

    before(() => {
      endpoint = `https://${zone.slug}.${COWORK_ACCOUNT.domain}/api/v1/kb/${zone.permanentKb.id}`;
      authHeader = getCoworkAuthHeader();

      cy.task('log', 'Ensuring permanent KB has exactly 3 e2e test resources');
      cy.request({
        method: 'GET',
        url: `${endpoint}/resources`,
        headers: authHeader,
      }).then((response) => {
        expect(response.status).to.eq(200);
        const testResources = response.body.resources?.filter((r) => r.slug?.startsWith('e2e-')) || [];

        const currentCount = testResources.length;
        cy.task('log', `Found ${currentCount} e2e test resources`);

        if (currentCount > 3) {
          cy.task('log', `Cleaning up ${currentCount - 3} excess resources`);
          testResources.slice(3).forEach((resource) => {
            cy.request({
              method: 'DELETE',
              url: `${endpoint}/resource/${resource.id}`,
              headers: authHeader,
              failOnStatusCode: false,
            });
          });
          cy.wait(2000);
        } else if (currentCount < 3) {
          cy.task('log', `Creating ${3 - currentCount} missing resources`);
          for (let i = currentCount + 1; i <= 3; i++) {
            cy.request({
              method: 'POST',
              url: `${endpoint}/resources`,
              headers: authHeader,
              failOnStatusCode: false,
              body: {
                slug: `e2e-resource-test-${i}`,
                title: `Test Resource ${i}.txt`,
                texts: {
                  text: {
                    body: `This is test resource number ${i}`,
                    format: 'PLAIN',
                  },
                },
              },
            });
          }
          cy.wait(5000);
        } else {
          cy.task('log', 'Perfect! Already have exactly 3 resources');
        }
      });
    });

    beforeEach(() => {
      cy.loginToCoworkKb(zone);
    });

    it('should display resources table with uploaded file', () => {
      cy.get('app-resource-table', { timeout: 5000 }).should('be.visible');
      cy.get('app-resource-table pa-table-row').should('have.length.at.least', 1);
      cy.get('app-resource-table').should('contain', 'Ready');
    });

    it('should open delete confirmation modal when clicking delete button', () => {
      cy.get('app-resource-table', { timeout: 5000 }).should('be.visible');
      cy.get('app-resource-table pa-button[icon="trash"]').first().click();
      cy.get('pa-confirmation-dialog').should('be.visible');
      cy.get('pa-confirmation-dialog').should('contain', 'Delete');
    });

    it('should remove resource from table after confirming delete', () => {
      cy.get('app-resource-table', { timeout: 5000 }).should('be.visible');
      cy.get('app-resource-table pa-table-row').then(($rows) => {
        const initialCount = $rows.length;
        cy.get('app-resource-table pa-button[icon="trash"]').first().click();
        cy.get('pa-confirmation-dialog [qa="confirmation-dialog-confirm-button"]').click();
        cy.wait(2000);
        cy.get('app-resource-table pa-table-row').should('have.length', initialCount - 1);
      });
    });

    it('should navigate between resources and history views', () => {
      cy.get('app-resource-table', { timeout: 5000 }).should('be.visible');
      cy.get('app-simple-kb .counters button.nav').contains('History').click();
      cy.get('app-history-table', { timeout: 5000 }).should('be.visible');
      cy.get('app-simple-kb .counters button.nav').contains('Your resources').click();
      cy.get('app-resource-table', { timeout: 5000 }).should('be.visible');
    });
  });
});
