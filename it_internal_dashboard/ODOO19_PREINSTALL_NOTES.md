# Odoo 19 Pre-install Notes

## Cleanup completed

- Replaced invalid cross-module imports with standard relative imports.
- Updated JSON controller routes from Odoo 18 `type="json"` to Odoo 19 `type="jsonrpc"`.
- Converted the legacy `_sql_constraints` declaration to `models.Constraint`.
- Removed duplicate XML record IDs and duplicate access-control CSV IDs.
- Removed bundled `node_modules`, `package.json`, and `package-lock.json` from the deployable addon.
- Declared the `requests` Python dependency in the manifest.
- Normalized manifest metadata and asset declarations.
- Removed unused imports and duplicate logger initialization.
- Verified Python compilation and XML parsing.

## Server prerequisite

Install the Python dependency in the same virtual environment used by Odoo:

```bash
pip install requests
```

## Recommended installation validation

```bash
./odoo-bin -c /path/to/odoo.conf -d YOUR_DATABASE \
  -i it_internal_dashboard --stop-after-init
```

Review the Odoo log for missing enterprise/custom dependencies and then test:

1. Internal client-action dashboards.
2. Dashboard record creation and weekly duplicate validation.
3. Public share-link generation and public workspace loading.
4. Zoho OAuth callback, manual synchronization, and scheduled synchronization.
5. Access rights for each dashboard security group.

## Important

Static validation was completed without booting this addon inside the user's exact Odoo 19 server and database. A final install test on staging is still required because database records, installed modules, and the exact Odoo build can expose runtime-only issues.
