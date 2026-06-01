const crypto = require('crypto');
const { waitForSignupEmail } = require('./email-helper');

async function performCoworkSignup({ accountsBase, hydraBase, appBase, clientId, redirectUri, email, password, company, fullname, recaptchaToken }) {
  const codeVerifier = crypto.randomBytes(32).toString('base64url');
  const codeChallenge = crypto.createHash('sha256').update(codeVerifier).digest('base64url');

  const startBody = new URLSearchParams({ email, app: appBase, fullname, company, workflow: 'cowork' });
  const startResp = await fetch(`${accountsBase}/api/auth/signup/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: startBody,
    redirect: 'manual',
  });
  const startLocation = startResp.headers.get('location');
  if (!startLocation) throw new Error(`signup/start failed (${startResp.status}): no Location header`);
  const signupToken = new URL(startLocation, appBase).searchParams.get('signup_token');
  if (!signupToken) throw new Error(`No signup_token in redirect: ${startLocation}`);

  const state = Buffer.from(JSON.stringify({ signup_token: signupToken })).toString('base64');

  // Hydra public URL is on oauth.{domain}, not accounts.{domain}
  const oauthParams = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: 'code',
    scope: 'openid offline_access',
    state,
    code_challenge: codeChallenge,
    code_challenge_method: 'S256',
  });
  const oauthResp = await fetch(`${hydraBase}/oauth2/auth?${oauthParams}`, { redirect: 'manual' });
  const oauthLocation = oauthResp.headers.get('location');
  if (!oauthLocation) throw new Error(`/oauth2/auth did not redirect (${oauthResp.status})`);

  // getSetCookie() is Node 19+; fall back to get('set-cookie') for older runtimes
  const hydraCookies = oauthResp.headers.getSetCookie
    ? oauthResp.headers.getSetCookie()
    : [oauthResp.headers.get('set-cookie')].filter(Boolean);

  const loginRedirectUrl = oauthLocation.startsWith('http') ? oauthLocation : `${accountsBase}${oauthLocation}`;
  let loginChallenge = new URL(loginRedirectUrl).searchParams.get('login_challenge');

  if (!loginChallenge) {
    // Fallback: follow one more redirect in case there's a backend intermediary
    const loginHandlerResp = await fetch(loginRedirectUrl, { redirect: 'manual' });
    const loginHandlerLocation = loginHandlerResp.headers.get('location');
    if (!loginHandlerLocation) throw new Error(`Login handler did not redirect (${loginHandlerResp.status})`);
    loginChallenge = new URL(loginHandlerLocation.startsWith('http') ? loginHandlerLocation : `${accountsBase}${loginHandlerLocation}`).searchParams.get('login_challenge');
    if (!loginChallenge) throw new Error(`No login_challenge in redirect chain: ${loginHandlerLocation}`);
  }

  const signupResp = await fetch(`${accountsBase}/api/auth/signup`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-STF-VALIDATION': recaptchaToken,
    },
    body: JSON.stringify({ password, login_challenge: loginChallenge }),
  });
  if (!signupResp.ok) {
    const body = await signupResp.text();
    throw new Error(`/api/auth/signup failed (${signupResp.status}): ${body}`);
  }

  const magicToken = await waitForSignupEmail(email, 150000);
  if (!magicToken) throw new Error('Timed out waiting for signup email');

  const magicResp = await fetch(`${accountsBase}/api/auth/magic?token=${encodeURIComponent(magicToken)}`, {
    method: 'POST',
  });
  if (!magicResp.ok) {
    const body = await magicResp.text();
    throw new Error(`/api/auth/magic failed (${magicResp.status}): ${body}`);
  }
  const magicBody = await magicResp.json();
  if (magicBody.action !== 'startonboarding') {
    throw new Error(`Unexpected magic action: ${magicBody.action} (body: ${JSON.stringify(magicBody)})`);
  }
  let consentUrl = magicBody.consent_url;

  const extractCookies = (resp) => {
    const setCookies = resp.headers.getSetCookie ? resp.headers.getSetCookie() : [resp.headers.get('set-cookie')].filter(Boolean);
    return setCookies.map((c) => c.split(';')[0]);
  };
  const mergeCookies = (base, newCookies) => {
    const map = new Map();
    [...base, ...newCookies].forEach((c) => {
      const eq = c.indexOf('=');
      if (eq > 0) map.set(c.substring(0, eq).trim(), c);
    });
    return Array.from(map.values()).join('; ');
  };

  let currentCookies = hydraCookies.map((c) => c.split(';')[0]);

  // Hydra skip_consent=true  → consent_url IS the callback URL (has ?code=...)
  // Hydra skip_consent=false → consent_url is Hydra consent page → backend consent → callback
  let authCode;
  const callbackBase = redirectUri;
  const extractCode = (url) => new URL(url, appBase).searchParams.get('code');

  if (consentUrl.startsWith(callbackBase)) {
    authCode = extractCode(consentUrl);
  } else {
    const consentResp = await fetch(consentUrl, {
      redirect: 'manual',
      headers: { Cookie: mergeCookies(currentCookies, []) },
    });
    currentCookies = mergeCookies(currentCookies, extractCookies(consentResp)).split('; ').filter(Boolean);
    const consentLocation = consentResp.headers.get('location') || '';

    if (consentLocation.startsWith(callbackBase)) {
      authCode = extractCode(consentLocation);
    } else {
      const consentPageUrl = consentLocation.startsWith('http') ? consentLocation : `${accountsBase}${consentLocation}`;
      const consentPageResp = await fetch(consentPageUrl, {
        redirect: 'manual',
        headers: { Cookie: currentCookies.join('; ') },
      });
      currentCookies = mergeCookies(currentCookies, extractCookies(consentPageResp)).split('; ').filter(Boolean);
      const consentPageLocation = consentPageResp.headers.get('location') || consentLocation;
      const consentChallenge = new URL(consentPageLocation, appBase).searchParams.get('consent_challenge');
      if (!consentChallenge) throw new Error(`No consent_challenge found in: ${consentPageLocation}`);

      const consentFormBody = new URLSearchParams({ consent_challenge: consentChallenge });
      consentFormBody.append('grant_scope', 'openid');
      consentFormBody.append('grant_scope', 'offline_access');

      const submitResp = await fetch(`${accountsBase}/api/auth/oauth/consent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: consentFormBody,
        redirect: 'manual',
      });
      const submitLocation = submitResp.headers.get('location');
      if (!submitLocation) throw new Error(`Consent submit did not redirect (${submitResp.status})`);

      // Consent submit may redirect back to Hydra /oauth2/auth with consent_verifier;
      // if so, follow that one more time (with all accumulated CSRF cookies)
      if (submitLocation.includes('/oauth2/auth') || submitLocation.includes('consent_verifier')) {
        const verifierResp = await fetch(submitLocation, {
          redirect: 'manual',
          headers: { Cookie: currentCookies.join('; ') },
        });
        const verifierLocation = verifierResp.headers.get('location');
        authCode = verifierLocation ? extractCode(verifierLocation) : null;
      } else {
        authCode = extractCode(submitLocation);
      }
    }
  }

  if (!authCode) throw new Error('Could not extract auth code from OAuth callback');

  const tokenBody = new URLSearchParams({
    grant_type: 'authorization_code',
    code: authCode,
    redirect_uri: redirectUri,
    client_id: clientId,
    code_verifier: codeVerifier,
  });
  const tokenResp = await fetch(`${hydraBase}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: tokenBody,
  });
  if (!tokenResp.ok) {
    const body = await tokenResp.text();
    throw new Error(`Token exchange failed (${tokenResp.status}): ${body}`);
  }
  const tokens = await tokenResp.json();
  if (!tokens.access_token) throw new Error(`No access_token in response: ${JSON.stringify(tokens)}`);

  return { accessToken: tokens.access_token, refreshToken: tokens.refresh_token, signupToken };
}

module.exports = { performCoworkSignup };
