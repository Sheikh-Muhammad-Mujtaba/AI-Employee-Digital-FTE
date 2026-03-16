/**
 * email-mcp/index.js
 * AI Employee Silver Tier — Gmail Sender
 *
 * Called by orchestrator.py as:
 *   node index.js --send   (JSON payload via stdin)
 *
 * Required env vars (loaded from parent process environment):
 *   GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN, DRY_RUN
 */

require('dotenv').config({ path: require('path').join(__dirname, '..', '.env') });
const { google } = require('googleapis');

function buildGmailClient() {
  const oauth2 = new google.auth.OAuth2(
    process.env.GMAIL_CLIENT_ID,
    process.env.GMAIL_CLIENT_SECRET,
    'http://localhost'
  );
  oauth2.setCredentials({ refresh_token: process.env.GMAIL_REFRESH_TOKEN });
  return google.gmail({ version: 'v1', auth: oauth2 });
}

function buildRawMessage(to, subject, body) {
  const lines = [
    `To: ${to}`,
    `Subject: ${subject}`,
    'Content-Type: text/plain; charset=utf-8',
    'MIME-Version: 1.0',
    '',
    body,
  ];
  return Buffer.from(lines.join('\r\n')).toString('base64url');
}

async function readStdin() {
  return new Promise((resolve) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', chunk => { data += chunk; });
    process.stdin.on('end', () => resolve(data));
  });
}

async function main() {
  const args = process.argv.slice(2);

  if (!args.includes('--send')) {
    console.error('Usage: node index.js --send  (JSON via stdin)');
    process.exit(1);
  }

  const raw = await readStdin();
  let payload;
  try {
    payload = JSON.parse(raw);
  } catch (e) {
    console.error(JSON.stringify({ success: false, error: 'Invalid JSON input' }));
    process.exit(1);
  }

  const { to, subject, body } = payload;
  if (!to || !subject) {
    console.error(JSON.stringify({ success: false, error: 'Missing required fields: to, subject' }));
    process.exit(1);
  }

  if (process.env.DRY_RUN === 'true') {
    console.log(JSON.stringify({ success: true, dry_run: true, to, subject }));
    return;
  }

  try {
    const gmail = buildGmailClient();
    const result = await gmail.users.messages.send({
      userId: 'me',
      requestBody: { raw: buildRawMessage(to, subject, body || '') },
    });
    console.log(JSON.stringify({ success: true, id: result.data.id, to, subject }));
  } catch (err) {
    console.error(JSON.stringify({ success: false, error: err.message }));
    process.exit(1);
  }
}

main().catch(err => {
  console.error(JSON.stringify({ success: false, error: err.message }));
  process.exit(1);
});
