/// <reference types="cypress" />

import { UI_STARTER } from '../../support/common';

describe('UI Starter', () => {
  it('should build UI Starter', () => {
    if (!UI_STARTER) {
      cy.log('Not the UI Starter environment');
      cy.on('fail', (err, runnable) => {
        cy.log(err.message);
        return false;
      });
      cy.request({ url: 'http://localhost:4173', failOnStatusCode: false }).should('be.false');
    } else {
      cy.visit('http://localhost:4173');
      cy.get('.nuclia-widget .sw-search-input').should('exist');
      cy.get('.sw-textarea textarea').click();
      cy.get('.sw-textarea textarea').type(`How to customize the widget?\n`, { force: true });
      cy.get('.sw-initial-answer').should('exist');
      cy.get('h3.result-title').should('exist');
    }
  });
});
