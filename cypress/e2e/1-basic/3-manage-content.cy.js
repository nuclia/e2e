/// <reference types="cypress" />

import { emptyKb, getAuthHeader, goTo, uploadContent } from '../../support/common';

function checkResourceWasAdded(endpoint, resourceTitle) {
  cy.request({
    method: 'GET',
    url: `${endpoint}/resources`,
    headers: getAuthHeader()
  }).then(response => {
    expect(response.status).to.eq(200);
    // make sure the resource we just added is there, without relying on the resource count which depends on the success of other tests
    expect(response.body['resources'].some((resource) => resource.title === resourceTitle)).to.be.true;
  });
}

describe('Manage content', () => {
  const endpoint = `https://europe-1.stashify.cloud/api/v1/kb/${emptyKb.id}`;
  const authHeader = getAuthHeader();

  before(() => {
    cy.request({
      method: 'GET',
      url: `${endpoint}/resources`,
      headers: authHeader
    }).then(response => {
      expect(response.status).to.eq(200);
      // make sure the resource we just added is there, without relying on the resource count which depends on the success of other tests
      let resourceCount = response.body['resources'].length;
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
    goTo('Resources list');

    cy.location('pathname').should('equal', `/at/testing/${emptyKb.name}/resources/processed`);

    // Upload file
    cy.task('log', 'Upload file');
    uploadContent('Upload files');
    cy.get('#upload-file-chooser').attachFile('nuclia-logo.png');
    cy.get('app-upload-files').contains('Add').click();
    cy.get('pa-modal-title').contains('Upload queue').should('exist');
    cy.get('.status pa-icon[name="check"]', { timeout: 10000 }).should('exist');
    cy.get('app-upload-progress button[aria-label="Close"]').click();
    cy.get('.pa-toast-wrapper').should('contain', 'Upload successful');

    cy.task('log', 'Upload link');
    uploadContent('Add links');
    cy.get('app-create-link pa-input input').type('https://nuclia.com/contact/');
    cy.get('app-create-link button').contains('Add').click();
    cy.get('.pa-toast-wrapper').should('contain', 'Upload successful');

    cy.task('log', 'Check pending button and uploaded resources are there');
    cy.get('[data-cy="pending-access"] button').should('be.visible');
    checkResourceWasAdded(endpoint, 'nuclia-logo.png');
    checkResourceWasAdded(endpoint, 'https://nuclia.com/contact/');
  });

  it('should create a label set and classify a resource with it', () => {
    cy.loginToEmptyKb();

    cy.get('[data-cy="kb-endpoint"]').then($endpointContainer => {
      const endpoint = $endpointContainer.text().trim();

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
          expect(response.body['resources'].length).to.eq(3);

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

  it('should delete resources', () => {
    cy.loginToEmptyKb();
    goTo('Resources list');
    cy.task('log', 'Delete resources');
    cy.get('.resource-list pa-table-row').should('have.length.at.least', 1);
    cy.get('[data-cy="select-all"] input').click();
    cy.get('[data-cy="delete-selection"]').should('be.visible').click();
    cy.get('pa-confirmation-dialog button[aria-label="Delete"]').click();
    cy.get('[data-cy="spinner"]').should('be.visible');
  });
});
