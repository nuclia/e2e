import { goTo, STANDALONE_HEADER, STANDALONE_KB_NAME } from '../../support/common';

describe('NucliaDB Admin – KB management flow', () => {
  before(() => {
    cy.request({
      method: 'GET',
      url: 'http://localhost:8080/api/v1/kbs',
      headers: STANDALONE_HEADER
    }).then(response => {
      expect(response.status).to.eq(200);
      response.body['kbs'].forEach(kb => {
        cy.request({
          method: 'DELETE',
          url: `http://localhost:8080/api/v1/kb/${kb['uuid']}`,
          headers: STANDALONE_HEADER
        }).then(deleteResponse => expect(deleteResponse.status).to.eq(200));
      });
    });
  });

  it('should create a KB and delete it', () => {
    cy.visit(Cypress.env('NUCLIA_DB_ADMIN_URL'));

    cy.task('log', `Create a new standalone KB`);
    cy.get('[data-cy="create-kb-button"]').click();
    cy.get('[formcontrolname="title"] input').type(STANDALONE_KB_NAME);
    cy.get('[formgroupname="nuclia"] > div:first-child input').click();
    cy.get('[data-cy="new-kb-save-button"] button').should('be.enabled').click();
    cy.get('app-kb-switch').should('contain', STANDALONE_KB_NAME);

    cy.task('log', `Delete the created KB`);
    cy.get('app-standalone-menu').click();
    cy.get(`[data-cy="go-to-kb-list"`).click();
    cy.location('hash').should('equal', '#/admin/select/local');
    cy.get('[data-cy="kb-list-item"]').should('have.length', 1);
    cy.get('[data-cy="delete-kb-button"]').click();
    cy.get('[qa="confirmation-dialog-confirm-button"]').click();
    cy.get('[data-cy="no-kb-message"]').should('be.visible');
  });
});
