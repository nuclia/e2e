/// <reference types="cypress" />

const { COWORK_ACCOUNT } = require('../../support/common');

describe('Cowork Onboarding - Full Flow', () => {
  const ACCOUNTS_BASE = `https://accounts.${COWORK_ACCOUNT.domain}`;
  const HYDRA_BASE = `https://oauth.${COWORK_ACCOUNT.domain}`;
  const APP_BASE = `https://${COWORK_ACCOUNT.coworkDomain}`;
  const REDIRECT_URI = `${APP_BASE}/user/callback`;

  const timestamp = Date.now();
  const testAlias = `cowork-e2e-${timestamp}`;
  const testEmail = `nucliaemailvalidation+${testAlias}@gmail.com`;
  const testPassword = `E2Etest!${timestamp}`;
  // Fixed name — clearly automated, no real user would create this.
  // Slug is deterministic so we can delete it by known slug before each run.
  const testCompany = 'cypress-e2e-cowork';
  const testSlug = 'cypress-e2e-cowork';

  before(function () {
    if (Cypress.env('RUNNING_ENV') !== 'stage') this.skip();
    // Delete the fixed-slug test account if it exists from a previous interrupted run.
    // failOnStatusCode: false silently skips the 404 when there's nothing to clean up.
    cy.request({
      method: 'DELETE',
      url: `${ACCOUNTS_BASE}/api/manage/@account/${testSlug}`,
      headers: { Authorization: `Bearer ${Cypress.env('STAGE_ROOT_PAT_TOKEN')}` },
      failOnStatusCode: false,
    });
  });

  // No retries: a second attempt sends another email to the same alias, causing
  // Gmail to delay delivery and making both attempts time out.
  it('should complete full cowork onboarding flow with auto-account-creation', { retries: 0 }, () => {
    cy.task(
      'performCoworkSignup',
      {
        accountsBase: ACCOUNTS_BASE,
        hydraBase: HYDRA_BASE,
        appBase: APP_BASE,
        clientId: Cypress.env('OAUTH_CLIENT_ID'),
        redirectUri: REDIRECT_URI,
        email: testEmail,
        password: testPassword,
        company: testCompany,
        fullname: 'Cypress E2E',
        recaptchaToken: Cypress.env('GLOBAL_RECAPTCHA'),
      },
      { timeout: 180000 },
    ).then(({ accessToken, refreshToken, signupToken }) => {
      // Pre-load tokens into localStorage so the app recognises the session.
      // SIGNUP_DATA must be set manually — /user/onboarding has no canActivate guard.
      cy.visit(`${APP_BASE}/user/onboarding?signup_token=${signupToken}`, {
        onBeforeLoad(win) {
          win.localStorage.setItem('JWT_KEY', accessToken);
          win.localStorage.setItem('JWT_REFRESH_KEY', refreshToken);
          win.localStorage.setItem('SIGNUP_DATA', signupToken);
        },
      });

      cy.get('nus-zone-step', { timeout: 30000 }).should('be.visible');
      cy.get('nus-zone-step pa-radio', { timeout: 15000 }).should('be.visible');
      // cy.wait(300) lets the 200ms waitForRadios poll complete so the radio group subscribes
      // before the click — without it the form control is never updated and Next stays disabled.
      // eslint-disable-next-line cypress/no-unnecessary-waiting
      cy.wait(300);
      cy.get('nus-zone-step pa-radio').first().find('input[type="radio"]').check({ force: true });
      cy.get('nus-zone-step pa-button[kind="primary"]').should('not.be.disabled').click();

      cy.get('nus-embedding-model-step', { timeout: 30000 }).should('be.visible');
      cy.get('nus-embedding-model-step pa-button[kind="primary"]').click();

      cy.url({ timeout: 120000 }).should('include', '/simple');
      cy.get('app-simple-kb', { timeout: 15000 }).should('be.visible');
    });
  });

});
