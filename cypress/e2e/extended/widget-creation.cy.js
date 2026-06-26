/// <reference types="cypress" />

import { ACCOUNT, getAuthHeader, goTo } from '../../support/common';

const WIDGET_SLUG = 'test-widget';

describe('Widgets page', () => {
  ACCOUNT.availableZones.forEach((zone) => {
    before(() => {
      const endpoint = `https://${zone.slug}.${ACCOUNT.domain}/api/v1/account/${ACCOUNT.id}/kb/${zone.permanentKb.id}`;
      const authHeader = getAuthHeader();

      // clean up widgets
      cy.request({ method: 'GET', url: endpoint, headers: authHeader }).then((response) => {
        expect(response.status).to.eq(200);
        const searchConfigs = response.body.search_configs;
        if ((searchConfigs?.widgets || []).length > 0) {
          cy.task('log', `Delete widgets from previous tests on ${zone.slug}`);
          cy.request({
            method: 'PATCH',
            url: endpoint,
            headers: authHeader,
            body: { search_configs: { ...searchConfigs, widgets: [] } },
          }).then((response) => expect(response.status).to.eq(200));
        }
      });

      cy.login(zone);
    });

    describe(`on ${zone.slug}`, () => {
      it(`should allow to create a new widget and delete it`, () => {
        // Create widget
        goTo('go-to-widget');
        cy.get('pa-button').contains('Create widget').click();
        cy.get('pa-modal-dialog').should('be.visible');
        cy.get('pa-modal-dialog pa-input input').type(WIDGET_SLUG);
        cy.get('pa-modal-dialog pa-button').contains('Set up widget').click();
        cy.location('pathname').should('include', `/widgets/${WIDGET_SLUG}`);
        cy.get('.widget-form-page .page-title').should('contain', WIDGET_SLUG);

        // Delete widget
        goTo('go-to-widget');
        cy.get('pa-table-row').should('have.length', 1);
        cy.get('pa-table-cell-menu pa-button').click();
        cy.get('pa-table-cell-menu pa-option').contains('Delete').click();
        cy.get('[qa="confirmation-dialog-confirm-button"]').click();
        cy.get('pa-table-row').should('have.length', 0);
      });
    });
  });
});
