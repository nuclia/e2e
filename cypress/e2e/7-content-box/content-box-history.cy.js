/// <reference types="cypress" />

import { COWORK_ACCOUNT, getCoworkAuthHeader } from '../../support/common';

describe('Content-box History', () => {
  const zone = COWORK_ACCOUNT.availableZones[0];

  describe(`on ${zone.slug}`, () => {
    let endpoint;
    let authHeader;

    before(() => {
      endpoint = `https://${zone.slug}.${COWORK_ACCOUNT.domain}/api/v1/kb/${zone.permanentKb.id}`;
      authHeader = getCoworkAuthHeader();
    });

    beforeEach(() => {
      cy.loginToCoworkKb(zone);
    });

    it('should display history tab in step 3', () => {
      cy.get('app-resource-table', { timeout: 5000 }).should('be.visible');
      cy.get('app-simple-kb .counters .nav').should('have.length', 2);
      cy.get('app-simple-kb .counters button.nav').should('contain.text', 'History');
    });
  });
});
