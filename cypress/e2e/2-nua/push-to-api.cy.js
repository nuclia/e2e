/// <reference types="cypress" />
import { ACCOUNT } from '../../support/common';

describe('Push file', () => {
  it('pushes a file to NUA queue', () => {
    ACCOUNT.availableZones.forEach((zone) => {
      cy.fixture('nuclia-logo.png')
        .then((file) =>
          cy.request({
            method: 'POST',
            url: `https://${zone.slug}.${ACCOUNT.domain}/api/v1/processing/upload`,
            headers: { 'x-stf-nuakey': `Bearer ${zone.nuaKey}`, md5: 'fa7bfc3072bf547b3d3f5c75050adadf' },
            body: file
          })
        )
        .then((resp) => {
          expect(resp.status).to.eq(200);
          return cy.request({
            method: 'POST',
            json: true,
            url: `https://${zone.slug}.${ACCOUNT.domain}/api/v1/processing/push`,
            headers: { 'x-stf-nuakey': `Bearer ${zone.nuaKey}` },
            body: {
              filefield: { 'nuclia-logo.png': resp.body }
            }
          });
        });
    })
  });

  it('pulls results', () => {
    ACCOUNT.availableZones.forEach((zone) => {
      cy
        .request({
          method: 'GET',
          url: `https://${zone.slug}.${ACCOUNT.domain}/api/v1/processing/pull`,
          headers: { 'x-stf-nuakey': `Bearer ${zone.nuaKey}` }
        })
        .then((res) => expect(res.status).to.eq(200));
    });
  });
});
