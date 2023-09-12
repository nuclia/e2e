/// <reference types="cypress" />

import { closeViewer, goTo, onlyPermanentKb } from '../../support/common';
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
  before(() => onlyPermanentKb());

  it('should display status', () => {
    cy.login();
    cy.get('.total-resources').should('contain', '2');
  });

  describe('Resources list', () => {
    beforeEach(() => {
      cy.login();
      goTo('Resources list');
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
      cy.contains('Displayed columns').click();
      cy.get('pa-checkbox').contains('Classification').click();
      cy.get('pa-chip-closeable').should('contain', 'permanent');
    });
  });

  describe('Search', () => {
    beforeEach(() => {
      cy.login();
      goTo('Search');
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
