const { defineConfig } = require('cypress');

module.exports = defineConfig({
  reporter: 'cypress-mochawesome-reporter',
  video: false,
  screenshotsFolder: 'cypress/reports/assets',
  viewportWidth: 1260,
  viewportHeight: 800,
  reporterOptions: {
    overwrite: false,
    html: false,
    json: true
  },
  e2e: {
    baseUrl: 'https://stashify.cloud',
    setupNodeEvents(on) {
      // Enable ability to log to the terminal from the tests
      on('task', {
        log(message) {
          console.log(`    ${message}`);
          return null;
        }
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
      runMode: 1
    }
  }
});
