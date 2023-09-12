/// <reference types="cypress" />

describe('Create a new account', () => {
  it('allows to go to account creation', () => {
    cy.visit('/');
    cy.contains('Create').click();
    cy.get('[data-cy="signup-form"]').should('exist');
    cy.get('button[type="submit"]').should('be.disabled');
    cy.get(`[formcontrolname="name"] input`).type('Bruce Wayne');
    cy.get(`[formcontrolname="email"] input`).type('test@not-a-real-email.nuclia.com');
    cy.get(`[formcontrolname="password"] input`).type('Batman');
    cy.get('button[type="submit"]').should('be.enabled');
    cy.get('button[type="submit"]').click();
    cy.get('[qa="confirmation-title"]').should('contain', 'Check your emails!');
  });
});
