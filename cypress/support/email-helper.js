const { ImapFlow } = require('imapflow');
const PostalMime = require('postal-mime');

const SUBJECT_FILTER = { or: [{ subject: 'Welcome to Progress' }, { subject: 'Welcome to stashify' }] };

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Waits for a signup email to arrive in the Gmail inbox and extracts the magic token.
 * Uses Gmail IMAP with the nucliaemailvalidation@gmail.com account.
 *
 * @param {string} emailAlias - Full email address with alias (e.g., nucliaemailvalidation+test123@gmail.com)
 * @param {number} timeout - Maximum time to wait in milliseconds (default: 60000)
 * @returns {Promise<string|null>} The magic token from the email, or null if not found
 */
async function waitForSignupEmail(emailAlias, timeout = 60000) {
  if (!process.env.GMAIL_APP_PASSWORD) {
    throw new Error('GMAIL_APP_PASSWORD environment variable is not set');
  }

  const clientConfig = {
    host: 'imap.gmail.com',
    port: 993,
    secure: true,
    auth: { user: 'nucliaemailvalidation@gmail.com', pass: process.env.GMAIL_APP_PASSWORD },
    logger: false,
  };

  const startTime = Date.now();

  while (Date.now() - startTime < timeout) {
    const client = new ImapFlow(clientConfig);
    try {
      await client.connect();
      const lock = await client.getMailboxLock('INBOX');
      try {
        const messages = await client.search({ unseen: true, to: emailAlias, ...SUBJECT_FILTER });

        if (messages.length > 0) {
          const uid = messages[messages.length - 1];
          const { source } = await client.fetchOne(uid, { source: true }, { uid: true });
          await client.messageFlagsAdd(uid, ['\\Seen'], { uid: true });

          const parsed = await PostalMime.parse(source);
          const haystack = parsed.html || parsed.text || '';
          const match = haystack.match(/user\/signup\?token=([^"&\s<>]+)/);
          if (match) return match[1];
        }
      } finally {
        lock.release();
      }
    } catch (error) {
      console.error(`[EMAIL] Error polling inbox, retrying in 5s: ${error.message}`);
    } finally {
      try { await client.logout(); } catch (_) { /* ignore */ }
    }

    await delay(5000);
  }

  console.error(`[EMAIL] Timeout: no email for ${emailAlias} after ${timeout}ms`);
  return null;
}

module.exports = { waitForSignupEmail };
