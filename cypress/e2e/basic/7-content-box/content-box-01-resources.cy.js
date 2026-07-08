/// <reference types="cypress" />

import { COWORK_ACCOUNT, getCoworkAuthHeader } from '../../../support/common';

describe('Content-box Resources', () => {
  const zone = COWORK_ACCOUNT.availableZones[0];

  describe(`on ${zone.slug}`, () => {
    before(() => {
      const endpoint = `https://${zone.slug}.${COWORK_ACCOUNT.domain}/api/v1/kb/${zone.permanentKb.id}`;
      const authHeader = getCoworkAuthHeader();

      cy.task('log', 'Ensuring permanent KB has at least 3 e2e test resources');

      const resourceBodies = [
        'Artificial intelligence is transforming how we search and retrieve information from large document collections. Modern RAG systems combine vector search with generative models to provide accurate, contextual answers.',
        'Knowledge management has evolved significantly with the advent of semantic search technologies. Organizations can now surface relevant content instantly, reducing the time employees spend searching for information.',
        'Natural language processing enables machines to understand and generate human language with remarkable accuracy. Applications range from document summarization to conversational agents capable of complex reasoning.',
      ];
      cy.request({
        method: 'GET',
        url: `${endpoint}/resources`,
        headers: authHeader,
      }).then((response) => {
        expect(response.status).to.eq(200);
        const testResources = response.body.resources?.filter((r) => r.slug?.startsWith('e2e-')) || [];
        const currentCount = testResources.length;
        cy.task('log', `Found ${currentCount} e2e test resources`);

        if (currentCount < 3) {
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
                    body: resourceBodies[i - 1],
                    format: 'PLAIN',
                  },
                },
              },
            })
          }
          cy.wait(5000);
        } else {
          cy.task('log', 'Already have 3 or more resources');
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

    it('should navigate between resources and history views', () => {
      cy.get('app-resource-table', { timeout: 5000 }).should('be.visible');
      cy.get('app-simple-kb .counters button.nav').contains('History').click();
      cy.get('app-history-table', { timeout: 5000 }).should('be.visible');
      cy.get('app-simple-kb .counters button.nav').contains('Your resources').click();
      cy.get('app-resource-table', { timeout: 5000 }).should('be.visible');
    });
  });
});
