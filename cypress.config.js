const { defineConfig } = require('cypress');
const { waitForSignupEmail } = require('./cypress/support/email-helper');
const { performCoworkSignup } = require('./cypress/support/cowork-signup');

module.exports = defineConfig({
  reporter: 'cypress-mochawesome-reporter',
  video: false,
  screenshotsFolder: 'cypress/reports/assets',
  viewportWidth: 1461,
  viewportHeight: 800,
  reporterOptions: {
    overwrite: false,
    html: false,
    json: true,
  },
  e2e: {
    setupNodeEvents(on, config) {
      // Bridge Cypress env vars to process.env so task code can access them
      if (config.env) {
        for (const [key, value] of Object.entries(config.env)) {
          if (!process.env[key]) process.env[key] = value;
        }
      }
      // Enable ability to log to the terminal from the tests
      on('task', {
        log(message) {
          console.log(`    ${message}`);
          return null;
        },
        waitForEmail: ({ emailAlias, timeout }) => waitForSignupEmail(emailAlias, timeout),
        performCoworkSignup,
      });
      // Load plugins
      require('cypress-mochawesome-reporter/plugin')(on);
    },
    env: {
      STANDALONE_KB_NAME: 'standalone-kb',
      NUCLIA_DB_ADMIN_URL: 'http://0.0.0.0:8080/admin',
    },
    retries: {
      openMode: 0,
      runMode: 1,
    },
  },
});
