import { goTo, STANDALONE_HEADER, STANDALONE_KB_NAME } from '../../support/common';

describe('NucliaDB admin – Manage content', () => {
  before(() => {
    // Delete existing KB if any and create a KB for Manage content purpose
    cy.request({
      method: 'GET',
      url: 'http://localhost:8080/api/v1/kbs',
      headers: STANDALONE_HEADER
    }).then(response => {
      expect(response.status).to.eq(200);
      const kbPayload = { 'slug': `${STANDALONE_KB_NAME}`, 'zone': 'local', 'title': `${STANDALONE_KB_NAME}` };
      if (response.body['kbs'].length > 0) {
        response.body['kbs'].forEach(kb => {
          cy.request({
            method: 'DELETE',
            url: `http://localhost:8080/api/v1/kb/${kb['uuid']}`,
            headers: STANDALONE_HEADER
          }).then(deleteResponse => {
            expect(deleteResponse.status).to.eq(200);
            return cy.request({
              method: 'POST',
              url: 'http://localhost:8080/api/v1/kbs',
              headers: STANDALONE_HEADER,
              body: kbPayload
            }).then((creationResponse) => expect(creationResponse.status).to.eq(201));
          });
        });
      } else {
        return cy.request({
          method: 'POST',
          url: 'http://localhost:8080/api/v1/kbs',
          headers: STANDALONE_HEADER,
          body: kbPayload
        }).then((creationResponse) => expect(creationResponse.status).to.eq(201));
      }
    });
  });

  it('should upload some content in the KB', () => {
    cy.visit(Cypress.env('NUCLIA_DB_ADMIN_URL'));
    cy.get('[data-cy="kb-list-item"]').should('have.length', 1).click();

    goTo('go-to-upload');
    cy.get('stf-upload-option[icon="file"]').click();
    cy.get('#upload-file-chooser').attachFile('nuclia-logo.png');
    cy.get('app-upload-files').contains('Add').click();
    cy.get('pa-modal-title').contains('Upload queue').should('exist');
    cy.get('.status pa-icon[name="check"]', { timeout: 10000 }).should('exist');
    cy.get('app-upload-progress button[aria-label="Close"]').click();
    cy.get('.pa-toast-wrapper').should('contain', 'Upload successful');
    cy.location('hash').should('contain', `/resources/pending`);
  });
});