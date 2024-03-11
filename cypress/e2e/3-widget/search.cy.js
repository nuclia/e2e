/// <reference types="cypress" />

import { ACCOUNT, closeViewer } from '../../support/common';
import {
  expectedResourceTitle,
  firstQuestion,
  nucliaSearchBarSelector,
  nucliaSearchResultsSelector,
  searchBarInputSelector,
  searchResultContainerSelector,
  searchResultTitle,
  suggestionResultSelector,
  viewerSelector
} from '../selectors/widget-selectors';

describe('Search', () => {
  ACCOUNT.availableZones.forEach((zone) => {
    describe(`on ${zone.slug}`, () => {
      beforeEach(() => {
        cy.visit(zone.searchUrl);
      });

      it('should show suggestions and open preview from it', () => {
        cy.get(nucliaSearchBarSelector).shadow().find('.sw-search-input input').type('Lamarr');
        cy.get(nucliaSearchBarSelector).shadow().find(suggestionResultSelector).should('have.length', 2);
        cy.get(nucliaSearchBarSelector).shadow().find(`${suggestionResultSelector}:first-child`).click();
        cy.get(nucliaSearchResultsSelector).shadow().find('.sw-viewer .header-title').should('contain', 'Lamarr Lesson plan.pdf');
        closeViewer();
      });

      it('should display results', () => {
        cy.get(nucliaSearchBarSelector).shadow().find(searchBarInputSelector).type(`${firstQuestion}\n`, { force: true });
        cy.get(nucliaSearchResultsSelector)
          .shadow()
          .find(`${searchResultContainerSelector} ${searchResultTitle}`, { timeout: 6000 })
          .should('have.length', 2);
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
});