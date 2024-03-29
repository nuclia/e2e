/// <reference types="cypress" />

import {
  viewerSelector,
  expectedResourceTitle,
  findInResourceInputSelector,
  firstQuery,
  nucliaSearchBarSelector,
  nucliaSearchResultsSelector,
  searchBarInputSelector,
  searchResultContainerSelector,
  searchResultLiSelector,
  secondQuery,
  searchResultTitle,
} from '../selectors/widget-selectors';
import { ACCOUNT } from '../../support/common';

describe('Find', () => {
  ACCOUNT.availableZones.forEach((zone) => {
    describe(`on ${zone.slug}`, () => {
      beforeEach(() => {
        cy.visit(zone.findUrl);
      });

      it('should display results, preview and allow to search paragraphs in the resource', () => {
        cy.get(nucliaSearchBarSelector).shadow().find(searchBarInputSelector).type(`${firstQuery}\n`, { force: true });
        cy.get(nucliaSearchResultsSelector)
          .shadow()
          .find(`${searchResultContainerSelector} ${searchResultTitle}`)
          .should('contain', expectedResourceTitle);
        cy.get(nucliaSearchResultsSelector)
          .shadow()
          .find(`${searchResultContainerSelector} ${searchResultLiSelector}`)
          .should('have.length.at.least', 1);

        // should allow to preview in the resource
        cy.get(nucliaSearchResultsSelector)
          .shadow()
          .find(`${searchResultContainerSelector} ${searchResultTitle}`)
          .contains(expectedResourceTitle)
          .click();
        cy.get(nucliaSearchResultsSelector).shadow().find(viewerSelector).should('contain', expectedResourceTitle);

        // should allow to search paragraphs in the resource
        cy.get(nucliaSearchResultsSelector).shadow().find(`${viewerSelector} .side-panel-button`).click();
        cy.get(nucliaSearchResultsSelector)
          .shadow()
          .find(`${viewerSelector} ${searchResultLiSelector}`)
          .should('have.length.at.least', 1);
        cy.get(nucliaSearchResultsSelector).shadow().find(`${viewerSelector} ${findInResourceInputSelector}`).click();
        cy.get(nucliaSearchResultsSelector)
          .shadow()
          .find(`${viewerSelector} ${findInResourceInputSelector}`)
          .type(`${secondQuery}\n`);
        cy.get(nucliaSearchResultsSelector)
          .shadow()
          .find(`${viewerSelector} ${searchResultLiSelector}`)
          .should('have.length.at.least', 1);
      });
    });
  });
});
