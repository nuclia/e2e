/// <reference types="cypress" />

import { goTo, KB_NAME, onlyPermanentKb } from '../../support/common';

describe('KB creation flow', () => {
  before(() => onlyPermanentKb());

  it('should allow to create a new kb', () => {
    cy.login();

    goTo('Manage account');
    goTo('Knowledge Boxes');
    cy.contains('Add Knowledge Box').click();
    cy.get('app-kb-add [formcontrolname="title"] input').type(KB_NAME);
    cy.get('app-kb-add [formcontrolname="description"] textarea').type('Some kb');
    cy.get('app-kb-add').contains('Next').click();
    cy.get('app-kb-add').contains('Save').click();
    cy.get(`a[href="/at/testing/europe-1/${KB_NAME}"]`, { timeout: 10000 }).should('contain', KB_NAME);
    cy.get(`a[href="/at/testing/europe-1/${KB_NAME}"]`).click();
    cy.location('pathname').should('equal', `/at/testing/europe-1/${KB_NAME}`);
    cy.get('app-kb-switch').should('contain', KB_NAME);
    cy.get('.state-container .title-s').should('contain', 'private');
  });

  it('should allow to delete the kb', () => {
    cy.loginToNewKb();
    goTo('Manage account');
    goTo('Knowledge Boxes');
    cy.get(`[data-cy="${KB_NAME}-link"]`).contains(KB_NAME);
    cy.get(`[data-cy="${KB_NAME}-delete"]`).click();
    cy.get('[qa="confirmation-dialog-confirm-button"]').click();
    cy.get('.account-kbs-list .account-kb').should('have.length', 2);
  });
});
