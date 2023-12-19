// ***********************************************
// This example commands.js shows you how to
// create various custom commands and overwrite
// existing commands.
//
// For more comprehensive examples of custom
// commands please read more here:
// https://on.cypress.io/custom-commands
// ***********************************************


import { emptyKb } from './common';
function login(kbName = 'permanent') {
  cy.visit(`/`, {
    onBeforeLoad(win) {
      // Store auth tokens
      win.localStorage.setItem('JWT_KEY', Cypress.env('BEARER_TOKEN'))
      win.localStorage.setItem('NUCLIA_GETTING_STARTED_DONE', 'true');
    }
  });
  cy.contains(kbName).click();
  cy.get(`.kb-details .title-xxs`).should('contain', 'NucliaDB API endpoint')
}

// -- This is a parent command --
Cypress.Commands.add('login', () => login());
Cypress.Commands.add('loginToEmptyKb', () => login(emptyKb.name));


// -- This is a child command --
// Cypress.Commands.add('drag', { prevSubject: 'element'}, (subject, options) => { ... })
//
//
// -- This is a dual command --
// Cypress.Commands.add('dismiss', { prevSubject: 'optional'}, (subject, options) => { ... })


// -- This will overwrite an existing command --
Cypress.Commands.overwrite('visit', (originalFn, url, options) => {
  return originalFn(url, {
    ...options,
    onBeforeLoad(win) {
      if (typeof options?.onBeforeLoad === 'function') {
        options.onBeforeLoad(win);
      }
      Object.defineProperty(win.navigator, 'languages', {
        value: ['en']
      });
    }
  });
});

import 'cypress-file-upload';
import 'cypress-real-events/support';

const LocalStorage = require('./localstorage');

const register = (Cypress, cy, localStorage) => {
  const localStorageCommands = new LocalStorage(localStorage, cy);

  // Register commands
  LocalStorage.cypressCommands.forEach((commandName) => {
    Cypress.Commands.add(commandName, localStorageCommands[commandName].bind(localStorageCommands));
  });
};

register(Cypress, cy, localStorage);
