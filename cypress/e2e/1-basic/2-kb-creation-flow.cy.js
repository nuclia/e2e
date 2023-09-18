/// <reference types="cypress" />

import { getAuthHeader, goTo, KB_NAME, onlyPermanentKb } from '../../support/common';

describe('KB creation flow', () => {
  before(() => onlyPermanentKb());

  it('should allow to create a new kb', () => {
    cy.login();

    goTo('Manage account');
    goTo('Knowledge boxes');
    cy.contains('Add knowledge box').click();
    cy.get('app-kb-add [formcontrolname="title"] input').type(KB_NAME);
    cy.get('app-kb-add [formcontrolname="description"] textarea').type('Some kb');
    cy.get('app-kb-add').contains('Next').click();
    cy.get('app-kb-add').contains('Save').click();
    cy.get(`a[href="/at/testing/${KB_NAME}"]`, { timeout: 10000 }).should('contain', KB_NAME);
    cy.get(`a[href="/at/testing/${KB_NAME}"]`).click();
    cy.location('pathname').should('equal', `/at/testing/${KB_NAME}`);
    cy.get('app-kb-switch').should('contain', KB_NAME);
    cy.get('.state-container .title-s').should('contain', 'private');
  });

  it('should import a dataset, create a label set and set label on resource', () => {
    cy.loginToNewKb();
    cy.get('[data-cy="kb-endpoint"]').then($endpointContainer => {
      const endpoint = $endpointContainer.text().trim();

      cy.task('log', 'Import dataset');
      goTo('Resources list');
      cy.get('.dataset-picker pa-select').click();
      cy.get('pa-option[id="permanent"]').click();
      cy.contains('Import data').click();
      cy.get('.resource-list-content pa-table-row', { timeout: 150000 }).should('have.length', 2);

      cy.task('log', 'Create a label set');
      goTo('Classification');
      cy.contains('Add new').click();
      cy.get('input#title-input').type('Heroes');
      cy.get('.pa-toggle').contains('Resources').click();
      cy.get('.label-content.unsaved-label input').type('Catwoman{enter}');
      cy.get('.label-content.unsaved-label input').type('Poison Ivy{enter}');
      cy.contains('Save').click();
      cy.get('pa-expander-header').should('contain', 'Heroes');

      cy.task('log', 'Set labels on resources');
      goTo('Resources list');
      cy.get('[data-cy="resource-title"]').first().invoke('text').then(resourceTitle => {
        const title = resourceTitle.trim();

        cy.get('[data-cy="menu-button"] button').first().click();
        cy.get('ul.pa-menu li').contains('Edit').click();
        cy.get('pa-button[icon="label"]').click();
        cy.get('nav ul li').contains('Resource').click();
        cy.contains('Select the labels').click();
        cy.contains('Heroes').click();
        cy.contains('Catwoman').click();
        cy.get('body').type('{esc}');
        cy.contains('Save').click();
        cy.get('.pa-toast-wrapper').should('contain', 'Resource saved');
        cy.request({
          method: 'GET',
          url: `${endpoint}/resources`,
          headers: getAuthHeader()
        }).then(response => {
          expect(response.status).to.eq(200);
          expect(response.body['resources'].length).to.eq(2);

          response.body['resources'].forEach((resource) => {
            if (resource.title === title) {
              expect(resource['usermetadata']['classifications']).to.deep.equal([{
                labelset: 'heroes',
                label: 'Catwoman',
                cancelled_by_user: false
              }], 'includes the label added');
            }
          });
        });
      })
    });
  });

  it('should allow to delete the kb', () => {
    cy.loginToNewKb();
    goTo('Manage account');
    goTo('Knowledge boxes');
    cy.get(`[data-cy="${KB_NAME}-link"]`).contains(KB_NAME);
    cy.get(`[data-cy="${KB_NAME}-delete"]`).click();
    cy.get('[qa="confirmation-dialog-confirm-button"]').click();
    cy.get('.account-kbs-list .account-kb').should('have.length', 2);
  });
});
