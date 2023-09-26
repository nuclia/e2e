/// <reference types="cypress" />

import { goTo, KB_NAME, onlyPermanentKb } from '../../support/common';

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

  it('should import a dataset', () => {
    cy.loginToNewKb();
    cy.task('log', 'Import dataset');
    goTo('Resources list');
    cy.get('.dataset-picker pa-select').click();
    cy.get('pa-option[id="permanent"]').click();
    cy.contains('Import data').click();
    cy.get('.resource-list-content pa-table-row', { timeout: 150000 }).should('have.length', 2);
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
