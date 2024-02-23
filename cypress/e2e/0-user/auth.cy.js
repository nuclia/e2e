/// <reference types="cypress" />

import { ACCOUNT, user } from '../../support/common';

describe('User Login', () => {
  it('should redirect unauthenticated user to login page', function() {
    cy.visit('/at/testing');
    cy.location('pathname').should('equal', '/user/login');
  });


  it('should redirect to kb selection page after login', () => {
    cy.visit('/');
    cy.get(`[formcontrolname="email"] input`).type(user.email,{ log: false });
    cy.get(`[data-cy="password"] input[type="password"]`).type(user.password,{ log: false });
    cy.get(`button[type='submit']`).click();
    cy.location('pathname').should('equal', `/select/${ACCOUNT.slug}`);
  });

  it('should allow a visitor to login and logout', () => {
    const permanentKb = ACCOUNT.availableZones[0].permanentKb;
    cy.visit('/');
    cy.get(`[formcontrolname="email"] input`).type(user.email,{ log: false });
    cy.get(`[data-cy="password"] input[type="password"]`).type(`${user.password}{enter}`,{ log: false });
    cy.get('a').contains(permanentKb.name).click();
    cy.location('pathname').should('equal', `/at/${ACCOUNT.slug}/${permanentKb.zone}/${permanentKb.slug}`);
    cy.get(`.kb-details .title-xxs`).should('contain', 'NucliaDB API endpoint')

    // logout
    cy.get('[data-cy="user-menu"]').click();
    cy.get('[data-cy="logout"]').click();
    cy.location('pathname').should('equal', '/user/login');
  });

  it('should display login errors', () => {
    cy.visit('/');
    cy.get(`[formcontrolname="email"] input`).type('user').blur().focus().clear().blur();
    cy.get('[formcontrolname="email"] .pa-field-help-error').should('be.visible').and('contain', 'Required field');

    cy.get(`[data-cy="password"] input[type="password"]`).type('wrong password').clear().blur();
    cy.get('[data-cy="password"] .pa-field-help-error').should('be.visible').and('contain', 'Required field');

    cy.get(`button[type='submit']`).should('be.disabled');
  });
  
  it('should error for an invalid user', () => {
    cy.visit('/');
    cy.get(`[formcontrolname="email"] input`).type('wrong-email@gmail.com',{ log: false });
    cy.get(`[data-cy="password"] input[type="password"]`).type('invalid{enter}',{ log: false });
    cy.get(`[data-cy="login-error"]`).should('contain', 'Authentication error.').and('contain', 'Please try again or reset your password below.')
  });

  it('should error for an invalid password for existing user', () => {
    cy.visit('/');
    cy.get(`[formcontrolname="email"] input`).type(user.email,{ log: false });
    cy.get(`[data-cy="password"] input[type="password"]`).type('invalid{enter}',{ log: false });
    cy.get(`[data-cy="login-error"]`).should('contain', 'Authentication error.').and('contain', 'Please try again or reset your password below.')
  });
});