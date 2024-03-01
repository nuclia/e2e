/// <reference types="cypress" />

import {
  answerContainerSelector,
  chatContainerSelector,
  chatInputSelector,
  chatQuestionSelector,
  chatWithYourDocsSelector,
  expectedResourceTitle,
  firstQuestion,
  initialAnswerSelector,
  nucliaSearchBarSelector,
  nucliaSearchResultsSelector,
  searchBarInputSelector,
  secondQuestion,
  answerSourceTitleSelector,
  answerCitationSelector,
} from '../selectors/widget-selectors';
import { ACCOUNT } from '../../support/common';

describe('Ask', () => {
  ACCOUNT.availableZones.forEach((zone) => {
    describe(`on ${zone.slug}`, () => {
      beforeEach(() => {
        cy.visit(zone.askUrl);
      });

      it('should display initial answer and allow to chat with your docs', () => {
        cy.get(nucliaSearchBarSelector).shadow().find(searchBarInputSelector).click();
        cy.get(nucliaSearchBarSelector)
          .shadow()
          .find(searchBarInputSelector)
          .type(`${firstQuestion}\n`, { force: true });
        cy.get(nucliaSearchResultsSelector)
          .shadow()
          .find(`${initialAnswerSelector} ${answerContainerSelector}`, { timeout: 10000 })
          .should('exist');

        // chat with your doc
        cy.get(nucliaSearchResultsSelector)
          .shadow()
          .find(`${initialAnswerSelector} ${chatWithYourDocsSelector}`)
          .click();
        cy.get(nucliaSearchResultsSelector)
          .shadow()
          .find(`${chatContainerSelector} ${chatQuestionSelector}`)
          .should('contain', firstQuestion);
        cy.get(nucliaSearchResultsSelector)
          .shadow()
          .find(`${chatContainerSelector} ${answerContainerSelector}`)
          .should('have.length.at.least', 1);

        cy.get(nucliaSearchResultsSelector)
          .shadow()
          .find(`${chatContainerSelector} ${chatInputSelector}`)
          .type(`${secondQuestion}\n`);
        cy.get(nucliaSearchResultsSelector)
          .shadow()
          .find(`${chatContainerSelector} ${chatQuestionSelector}`)
          .should('have.length.at.least', 1)
          .and('contain', secondQuestion);
        cy.get(nucliaSearchResultsSelector)
          .shadow()
          .find(`${chatContainerSelector} ${answerContainerSelector}`)
          .should('have.length.at.least', 1);
      });

      it('should display citations and search results that have been used to generate the answer', () => {
        cy.get(nucliaSearchBarSelector).shadow().find(searchBarInputSelector).click();
        cy.get(nucliaSearchBarSelector)
          .shadow()
          .find(searchBarInputSelector)
          .type(`${secondQuestion}\n`, { force: true });
        cy.get(nucliaSearchResultsSelector)
          .shadow()
          .find(`${initialAnswerSelector} ${answerContainerSelector}`, { timeout: 10000 })
          .should('exist');
        cy.get(nucliaSearchResultsSelector)
          .shadow()
          .find(`${initialAnswerSelector} ${answerCitationSelector}`)
          .should('contain', 1);
        cy.get(nucliaSearchResultsSelector)
          .shadow()
          .find(`${initialAnswerSelector} ${answerSourceTitleSelector}`)
          .should('contain', expectedResourceTitle);
      });
    });
  });
});
