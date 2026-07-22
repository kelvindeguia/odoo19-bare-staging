# Workable API Health Monitor for Odoo 19

Standalone Odoo 19 application for monitoring multiple Workable API accounts and webhook subscriptions.

## Features

- Multiple Workable subdomains and API tokens
- Independent webhook URL per API account
- API connection and subscription health checks
- Register, re-register, and remove subscriptions
- HMAC SHA-256 webhook signature validation
- Webhook event audit log
- Scheduled check every 15 minutes
- Per-company record rules and administrator/user security groups
- Chatter alerts to selected Odoo users after a configurable failure threshold

## Installation

1. Copy `workable_api_health_monitor` into an Odoo addons directory.
2. Restart Odoo.
3. Update the Apps list.
4. Install **Workable API Health Monitor**.
5. Assign either **Workable Monitor User** or **Workable Monitor Administrator** to users.
6. Open **Workable API Monitor > API Accounts** and add each token.

## Workable setup

Use only the account subdomain, such as `mycompany`, not a complete URL. The module calls:

`https://mycompany.workable.com/spi/v3/subscriptions`

The generated webhook endpoint is based on Odoo's `web.base.url`. Confirm that `web.base.url` is your externally accessible HTTPS domain before registering subscriptions.

By default, outgoing requests use `Authorization: Bearer <token>`. Select **Raw Authorization Value** when your Workable credential must be sent without the Bearer prefix.

Workable signs webhook payloads with HMAC SHA-256. When the **Webhook Secret** is empty, the module uses the API token as the signing key.

## Notes

- The account token requires `r_candidates` or `r_employees` scope to list or manage subscriptions.
- Stale-webhook status is only evaluated after at least one valid webhook has been received. This avoids falsely marking low-volume event subscriptions as stale immediately after setup.
- Tokens are masked in forms and limited to the administrator group, but they are stored in the Odoo database. Protect database backups and administrative access accordingly.
