/// <reference types="cypress" />

import { ACCOUNT, emptyKb, getAuthHeader, goTo, ZONES } from '../../support/common';

function checkResourceWasAdded(endpoint, resourceTitle) {
  cy.request({
    method: 'GET',
    url: `${endpoint}/resources`,
    headers: getAuthHeader(false)
  }).then(response => {
    expect(response.status).to.eq(200);
    // make sure the resource we just added is there, without relying on the resource count which depends on the success of other tests
    expect(response.body['resources'].some((resource) => resource.title === resourceTitle)).to.be.true;
  });
}

describe('Manage content', () => {
  const endpoint = `https://${ZONES['europe']}.${ACCOUNT.domain}/api/v1/kb/${emptyKb.id}`;
  const authHeader = getAuthHeader();

  before(() => {
    // clean up resources
    cy.request({
      method: 'GET',
      url: `${endpoint}/resources`,
      headers: authHeader
    }).then(response => {
      expect(response.status).to.eq(200);
      const resourceCount = response.body['resources'].length;
      if (resourceCount > 0) {
        // This will be output to terminal
        cy.task('log', `Delete ${resourceCount} resources from previous tests`);
        response.body['resources'].forEach(resource => {
          cy.request({
            method: 'DELETE',
            url: `${endpoint}/resource/${resource.id}`,
            headers: authHeader
          }).then(deleteResponse => expect(deleteResponse.status).to.eq(204));
        });
      }
    });
  });

  it('should use the API to upload a file', () => {
    cy.request({
      method: 'POST',
      url: `${endpoint}/resources`,
      headers: {
        ...authHeader,
        'x-synchronous': 'true'
      },
      body: {
        title: 'hello.txt'
      }
    }).then(resourceResponse => {
      expect(resourceResponse.status).to.eq(201);
      const resourceId = resourceResponse.body.uuid;
      cy.fixture('hello.txt').then(file => cy.request({
        method: 'POST',
        url: `${endpoint}/resource/${resourceId}/file/hello/upload`,
        headers: {
          ...authHeader,
          'x-md5': ['8b1a9953c4611296a827abf8c47804d7'],
          'x-synchronous': 'true'
        },
        body: file
      }).then((resp) => {
        expect(resp.status).to.eq(201);
        checkResourceWasAdded(endpoint, 'hello.txt');
      }));
    });
  });

  it('should upload content from the UI', () => {
    cy.loginToEmptyKb();
    goTo('go-to-upload');

    // Upload file
    cy.task('log', 'Upload file');

    cy.get('stf-upload-option[icon="file"]').click();

    cy.get('#upload-file-chooser').attachFile('nuclia-logo.png');
    cy.get('app-upload-files').contains('Add').click();
    cy.get('pa-modal-title').contains('Upload queue').should('exist');
    cy.get('.status pa-icon[name="check"]', { timeout: 10000 }).should('exist');
    cy.get('app-upload-progress button[aria-label="Close"]').click();
    cy.get('.pa-toast-wrapper').should('contain', 'Upload successful');
    cy.location('pathname').should('equal', `/at/${ACCOUNT.slug}/${emptyKb.zone}/${emptyKb.name}/resources/pending`);

    cy.task('log', 'Upload link');
    goTo('go-to-upload');
    cy.get('stf-upload-option[icon="link"]').click();
    cy.get('app-create-link pa-input input').type('https://nuclia.com/contact/');
    cy.get('app-create-link button').contains('Add').click();
    cy.get('.pa-toast-wrapper').should('contain', 'Upload successful');
    cy.location('pathname').should('equal', `/at/${ACCOUNT.slug}/${emptyKb.zone}/${emptyKb.name}/resources/pending`);

    checkResourceWasAdded(endpoint, 'nuclia-logo.png');
    checkResourceWasAdded(endpoint, 'https://nuclia.com/contact/');
  });
});
