/// <reference types="cypress" />

import { closeViewer, getAuthHeader, goTo, onlyPermanentKb, permanentKb } from '../../support/common';
import {
  expectedResourceTitle,
  firstQuery,
  nucliaSearchBarSelector,
  nucliaSearchResultsSelector,
  searchBarInputSelector,
  searchResultContainerSelector,
  searchResultTitle,
  suggestionResultSelector,
  viewerSelector
} from '../selectors/widget-selectors';

describe('Resources', () => {
  before(() => {
    onlyPermanentKb();

    const endpoint = `https://europe-1.stashify.cloud/api/v1/kb/${permanentKb.id}`;
    const authHeader = getAuthHeader();

    // keep only permanent labels on resources
    cy.request({
      method: 'GET',
      url: `${endpoint}/resources`,
      headers: authHeader
    }).then(response => {
      expect(response.status).to.eq(200);
      response.body['resources'].forEach(resource => {
        cy.request({
          method: 'PATCH',
          url: `${endpoint}/resource/${resource.id}`,
          body: {
            usermetadata: {
              classifications: [{
                labelset: 'dataset',
                label: 'permanent',
                cancelled_by_user: false
              }], relations: []
            }
          },
          headers: authHeader
        }).then(patchResponse => expect(patchResponse.status).to.eq(200));
      });
    });

    // clean up labelsets
    cy.request({
      method: 'GET',
      url: `${endpoint}/labelsets`,
      headers: authHeader
    }).then(response => {
      expect(response.status).to.eq(200);
      const labelsets = Object.keys(response.body['labelsets']);
      if (labelsets.length > 1) {
        cy.task('log', `Delete ${labelsets.length - 1} label sets from previous tests`);
        labelsets.filter(labelset => labelset !== 'dataset').forEach(labelset => {
          cy.request({
            method: 'DELETE',
            url: `${endpoint}/labelset/${labelset}`,
            headers: authHeader
          }).then(deleteResponse => expect(deleteResponse.status).to.eq(200));
        });
      }
    });
  });

  it('should display status', () => {
    cy.login();
    cy.get('.total-resources').should('contain', '2');
  });

  describe('Resources list', () => {
    beforeEach(() => {
      cy.login();
      goTo('go-to-resources');
    });

    it('should list existing resources', () => {
      cy.get('.resource-list pa-table-row').should('have.length', 2);
    });

    it('should allow to preview', () => {
      cy.contains('Lamarr Lesson plan.pdf').click();
      cy.get('.edit-resource > header').should('contain', 'Lamarr Lesson plan.pdf');
      cy.get('.edit-resource .main-container').should('contain', 'Hedy Lamarr, An Inventive Mind');
    });

    it('should show labels on resources', () => {
      cy.get('[data-cy="visible-columns-dropdown"]').click();
      cy.get('pa-checkbox').contains('Classification').click();
      cy.get('pa-chip-closeable').should('contain', 'permanent');
    });
  });

  describe('Classification', () => {
    beforeEach(() => {
      cy.login();
    });

    it('should list existing label set', () => {
      goTo('go-to-settings');
      goTo('go-to-classification');
      cy.get('.label-sets-management pa-expander').contains('dataset').click();
      cy.get('.label-sets-management pa-expander .labels').contains('permanent');
    });

    it('should create a label set', () => {
      const labelset = 'Heroes';
      const label = 'Catwoman';
      goTo('go-to-settings');
      goTo('go-to-classification');
      cy.get('[data-cy="add-label-set"]').click();
      cy.get('input#title-input').type(labelset);
      cy.get('.pa-toggle').contains('Resources').click();
      cy.get('.label-content.unsaved-label input').type(`${label}{enter}`);
      cy.get('.label-content.unsaved-label input').type('Poison Ivy{enter}');
      cy.get('[data-cy="save-label-set"]').click();
      cy.get('pa-expander-header').should('contain', 'Heroes');
    });
  });

  describe('Search', () => {
    beforeEach(() => {
      cy.login();
      goTo('go-to-search');
    });

    it('should show suggestions and open preview from it', () => {
      cy.get(nucliaSearchBarSelector).shadow().find('.sw-search-input input').type('Lamarr');
      cy.get(nucliaSearchBarSelector).shadow().find(suggestionResultSelector).should('have.length', 2);
      cy.get(nucliaSearchBarSelector).shadow().find(`${suggestionResultSelector}:first-child`).click();
      cy.get(nucliaSearchResultsSelector).shadow().find('.sw-viewer .header-title').should('contain', 'Lamarr Lesson plan.pdf');
      closeViewer();
    });

    it('should display results', () => {
      cy.get(nucliaSearchBarSelector).shadow().find(searchBarInputSelector).type(`${firstQuery}\n`, { force: true });
      cy.get(nucliaSearchResultsSelector)
        .shadow()
        .find(`${searchResultContainerSelector} ${searchResultTitle}`)
        .should('have.length', 1);
      cy.get(nucliaSearchResultsSelector)
        .shadow()
        .find(`${searchResultContainerSelector} ${searchResultTitle}`)
        .should('contain', expectedResourceTitle);
      cy.get(nucliaSearchResultsSelector)
        .shadow()
        .find(`${searchResultContainerSelector} ${searchResultTitle}`)
        .contains(expectedResourceTitle)
        .click();
      cy.get(nucliaSearchResultsSelector)
        .shadow()
        .find(`${viewerSelector} .header-title .title-m`)
        .should('contain', expectedResourceTitle);
      closeViewer();
    });
  });
});
