/// <reference types="cypress" />

import { COWORK_ACCOUNT, getCoworkAuthHeader } from '../../support/common';

describe('Content-box Upload', () => {
  const zone = COWORK_ACCOUNT.availableZones[0];

  describe(`on ${zone.slug}`, () => {
    let endpoint;
    let authHeader;

    before(() => {
      if (Cypress.env('RUNNING_ENV') !== 'stage') this.skip();
      endpoint = `https://${zone.slug}.${COWORK_ACCOUNT.domain}/api/v1/kb/${zone.permanentKb.id}`;
      authHeader = getCoworkAuthHeader();
    });

    beforeEach(() => {
      cy.loginToCoworkKb(zone);
    });

    it('should display "Upload files" button in step 3', () => {
      cy.get('app-resource-table', { timeout: 5000 }).should('be.visible');
      cy.get('.footer pa-button').contains('Upload').should('be.visible');
    });

    it('should upload a file when selected', () => {
      const fileName = 'e2e-upload-test.txt';
      
      cy.get('input[type="file"]').attachFile('hello.txt');
      
      cy.wait(2000);
      
      cy.request({
        method: 'GET',
        url: `${endpoint}/resources`,
        headers: authHeader,
      }).then((response) => {
        expect(response.status).to.eq(200);
        const uploadedFile = response.body.resources?.find((r) => 
          r.title?.includes('hello.txt')
        );
        expect(uploadedFile).to.exist;
        
        if (uploadedFile) {
          cy.task('log', `Cleaning up uploaded file: ${uploadedFile.id}`);
          cy.request({
            method: 'DELETE',
            url: `${endpoint}/resource/${uploadedFile.id}`,
            headers: authHeader,
            failOnStatusCode: false,
          });
        }
      });
    });
  });
});
