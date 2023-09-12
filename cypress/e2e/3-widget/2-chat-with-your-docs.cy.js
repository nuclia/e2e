/// <reference types="cypress" />

import {
  answerContainerSelector,
  chatContainerSelector,
  chatInputSelector,
  chatQuestionSelector,
  chatWithYourDocsSelector,
  expectedResourceTitle,
  firstQuery,
  initialAnswerSelector,
  nucliaSearchBarSelector,
  nucliaSearchResultsSelector,
  searchBarInputSelector,
  searchResultLiSelector,
  secondQuery,
  searchResultTitle,
} from '../selectors/widget-selectors';

describe('Chat with your docs', () => {
  beforeEach(() => {
    cy.visit('https://nuclia.github.io/frontend/e2e/widget.html');
  });

  it('should display initial answer and allow to chat with your docs', () => {
    cy.get(nucliaSearchBarSelector).shadow().find(searchBarInputSelector).click();
    cy.get(nucliaSearchBarSelector).shadow().find(searchBarInputSelector).type(`${firstQuery}\n`, { force: true });
    cy.get(nucliaSearchResultsSelector)
      .shadow()
      .find(`${initialAnswerSelector} ${answerContainerSelector}`)
      .should('exist');
    cy.get(nucliaSearchResultsSelector)
      .shadow()
      .find(`${initialAnswerSelector} ${searchResultTitle}`)
      .should('contain', expectedResourceTitle);
    cy.get(nucliaSearchResultsSelector)
      .shadow()
      .find(`${initialAnswerSelector} ${searchResultLiSelector}`)
      .should('have.length', 11);

    // chat with your doc
    cy.get(nucliaSearchResultsSelector).shadow().find(`${initialAnswerSelector} ${chatWithYourDocsSelector}`).click();
    cy.get(nucliaSearchResultsSelector)
      .shadow()
      .find(`${chatContainerSelector} ${chatQuestionSelector}`)
      .should('contain', firstQuery);
    cy.get(nucliaSearchResultsSelector)
      .shadow()
      .find(`${chatContainerSelector} ${answerContainerSelector}`)
      .should('have.length', 1);

    cy.get(nucliaSearchResultsSelector)
      .shadow()
      .find(`${chatContainerSelector} ${chatInputSelector}`)
      .type(`${secondQuery}\n`);
    cy.get(nucliaSearchResultsSelector)
      .shadow()
      .find(`${chatContainerSelector} ${chatQuestionSelector}`)
      .should('have.length', 2)
      .and('contain', secondQuery);
    cy.get(nucliaSearchResultsSelector)
      .shadow()
      .find(`${chatContainerSelector} ${answerContainerSelector}`)
      .should('have.length', 2);
  });
});
