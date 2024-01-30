/// <reference types="cypress" />
describe('Push file', () => {
  it('pushes a file to NUA queue', () => {
    cy.fixture('nuclia-logo.png')
      .then((file) =>
        cy.request({
          method: 'POST',
          url: `https://europe-1.stashify.cloud/api/v1/processing/upload`,
          headers: { 'x-stf-nuakey': `Bearer ${Cypress.env('NUA_KEY')}`, md5: 'fa7bfc3072bf547b3d3f5c75050adadf' },
          body: file
        })
      )
      .then((resp) => {
        expect(resp.status).to.eq(200);
        return cy.request({
          method: 'POST',
          json: true,
          url: `https://europe-1.stashify.cloud/api/v2/processing/push`,
          headers: { 'x-stf-nuakey': `Bearer ${Cypress.env('NUA_KEY')}` },
          body: {
            filefield: { 'nuclia-logo.png': resp.body }
          }
        });
      });
  });

  it('pulls results', () => {
    cy
      .request({
        method: 'GET',
        url: `https://europe-1.stashify.cloud/api/v1/processing/pull`,
        headers: { 'x-stf-nuakey': `Bearer ${Cypress.env('NUA_KEY')}` }
      })
      .then((res) => expect(res.status).to.eq(200));
  });
});
