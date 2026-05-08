/// <reference types="cypress" />

const { ACCOUNT } = require('../../support/common');

describe('Create a new account', () => {
  it('allows to go to account creation', () => {
    cy.request({
      method: 'POST',
      url: `https://accounts.${ACCOUNT.domain}/api/auth/signup/start`,
      body: {
        app: `https://rag.${ACCOUNT.domain}`,
        email: 'test@not-a-real-email.nuclia.com',
        fullname: 'Bruce Wayne',
        company: 'DC Comics',
      },
      form: true,
      followRedirect: false,
    }).then((response) => {
      const redirect = response.headers.location;
      expect(redirect.startsWith(`https://rag.${ACCOUNT.domain}`)).to.eq(true);
      cy.visit(redirect);
      cy.get('*[aria-label="Cookie banner"] button#onetrust-accept-btn-handler').click();
      cy.get('button[type="submit"]').should('be.disabled');
      cy.get(`[formcontrolname="password"] input`).type('Batman12345678!');
      cy.get('button[type="submit"]').should('be.enabled');
      cy.get('button[type="submit"]').click();
      cy.get('[qa="confirmation-title"]').should('contain', 'Check your email inbox!');
    });
  });
});
